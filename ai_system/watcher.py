import time
import re
import pickle
import csv
import os
from mcrcon import MCRcon

log_path = "../logs/latest.log"

join_pattern = re.compile(r"(\w+) joined the game")
chat_pattern = re.compile(r"<(\w+)> (.+)")
death_pattern = re.compile(r"(\w+) (was slain by|was blown up by|drowned|fell)")
advancement_pattern = re.compile(r"(\w+) has made the advancement \[(.+)\]")

players = {}

LOW_THRESHOLD = 3
HIGH_THRESHOLD = 15
COOLDOWN_SECONDS = 30
DEATH_OVERRIDE_THRESHOLD = 3

# Switch between "rules" and "ml" to compare engines
ENGINE_MODE = "ml"

with open("event_model.pkl", "rb") as f:
    model = pickle.load(f)

session_log_path = "session_log.csv"

if not os.path.exists(session_log_path):
    with open(session_log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "player", "action_count", "idle_time", "session_length", "score", "engine_mode", "decision"])

def touch_player(name, event_type="action"):
    now = time.time()
    if name not in players:
        players[name] = {"session_start": now, "last_active": now, "action_count": 0, "last_event_time": 0, "death_count": 0, "advancement_count": 0}
    players[name]["last_active"] = now
    players[name]["action_count"] += 1
    if event_type == "death":
        players[name]["death_count"] += 1
    elif event_type == "advancement":
        players[name]["advancement_count"] += 1

def compute_score(name):
    p = players[name]
    now = time.time()
    idle_time = now - p["last_active"]
    score = (p["action_count"] * 2) - (idle_time * 0.1)
    return round(score, 2), round(idle_time, 1)

def send_command(cmd):
    with MCRcon("localhost", "test123", port=25575) as mcr:
        response = mcr.command(cmd)
        return response

def decide_with_rules(score):
    if score < LOW_THRESHOLD:
        return "reward"
    elif score > HIGH_THRESHOLD:
        return "challenge"
    return "none"

def decide_with_ml(name):
    p = players[name]
    now = time.time()
    idle_time = now - p["last_active"]
    session_length = now - p["session_start"]
    features = [[p["action_count"], idle_time, session_length]]
    return model.predict(features)[0]

def log_to_csv(name, score, decision):
    p = players[name]
    now = time.time()
    idle_time = round(now - p["last_active"], 1)
    session_length = round(now - p["session_start"], 1)
    with open(session_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([round(now, 1), name, p["action_count"], idle_time, session_length, score, ENGINE_MODE, decision])

def maybe_trigger_event(name, score):
    p = players[name]
    now = time.time()
    if now - p["last_event_time"] < COOLDOWN_SECONDS:
        return

    if ENGINE_MODE == "rules":
        decision = decide_with_rules(score)
    else:
        decision = decide_with_ml(name)

    if p["death_count"] >= DEATH_OVERRIDE_THRESHOLD and decision == "challenge":
        print(f"   [SAFETY] easing off {name} after {p['death_count']} deaths -> reward instead")
        decision = "reward"

    log_to_csv(name, score, decision)

    if decision == "reward":
        result = send_command(f"give {name} diamond 3")
        print(f"   [REWARD] {name} -> {result}")
        p["last_event_time"] = now
    elif decision == "challenge":
        result = send_command(f"execute at {name} run summon minecraft:zombie ~2 ~ ~2")
        print(f"   [CHALLENGE] {name} -> {result}")
        p["last_event_time"] = now

print(f"Watching for player activity... (engine: {ENGINE_MODE})\n")

with open(log_path, "r", encoding="utf-8") as f:
    f.seek(0, 2)
    while True:
        line = f.readline()
        if not line:
            time.sleep(1)
            continue

        join_match = join_pattern.search(line)
        chat_match = chat_pattern.search(line)
        death_match = death_pattern.search(line)
        advancement_match = advancement_pattern.search(line)

        name = None
        event_type = "action"
        if join_match:
            name = join_match.group(1)
        elif chat_match:
            name = chat_match.group(1)
        elif death_match:
            name = death_match.group(1)
            event_type = "death"
        elif advancement_match:
            name = advancement_match.group(1)
            event_type = "advancement"

        if name:
            touch_player(name, event_type)
            score, idle = compute_score(name)
            p = players[name]
            print(f"{name:<12} score: {score:>6} | idle: {idle:>5}s | deaths: {p['death_count']} | advancements: {p['advancement_count']}")
            maybe_trigger_event(name, score)