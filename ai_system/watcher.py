import time
import re
import pickle
import csv
import os
from mcrcon import MCRcon

log_path = "../logs/latest.log"

join_pattern = re.compile(r"(\w+) joined the game")
leave_pattern = re.compile(r"(\w+) left the game")
chat_pattern = re.compile(r"<(\w+)> (.+)")
death_pattern = re.compile(r"(\w+) (was slain by|was blown up by|drowned|fell)")
advancement_pattern = re.compile(r"(\w+) has (?:made the advancement|reached the goal|completed the challenge) \[(.+)\]")
players = {}

LOW_THRESHOLD = 3
HIGH_THRESHOLD = 15
CHALLENGE_HARD_THRESHOLD = 25
COOLDOWN_SECONDS = 30
DEATH_MERCY_THRESHOLD = 3
ADVANCEMENT_TIER_THRESHOLD = 3

# Switch between "static" (log only, no events), "rules", and "ml" to compare engines
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

def show_popup(name, title_text, subtitle_text, color="white", sound="entity.experience_orb.pickup"):
    title_cmd = f'title {name} title {{"text":"{title_text}","color":"{color}","bold":true}}'
    subtitle_cmd = f'title {name} subtitle {{"text":"{subtitle_text}","color":"gray"}}'
    sound_cmd = f'playsound minecraft:{sound} master {name}'
    send_command(title_cmd)
    send_command(subtitle_cmd)
    send_command(sound_cmd)

def decide_with_rules(name, score):
    p = players[name]
    if p["death_count"] >= DEATH_MERCY_THRESHOLD:
        return "mercy"
    elif p["advancement_count"] >= ADVANCEMENT_TIER_THRESHOLD:
        return "reward_tiered"
    elif score < LOW_THRESHOLD:
        return "reward"
    elif score > CHALLENGE_HARD_THRESHOLD:
        return "challenge_hard"
    elif score > HIGH_THRESHOLD:
        return "challenge_mild"
    return "none"

def decide_with_ml(name):
    p = players[name]
    now = time.time()
    idle_time = now - p["last_active"]
    session_length = now - p["session_start"]
    features = [[p["action_count"], idle_time, session_length, p["death_count"], p["advancement_count"]]]
    return model.predict(features)[0]

def log_to_csv(name, score, decision):
    p = players[name]
    now = time.time()
    idle_time = round(now - p["last_active"], 1)
    session_length = round(now - p["session_start"], 1)
    with open(session_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([round(now, 1), name, p["action_count"], idle_time, session_length, score, ENGINE_MODE, decision])

def log_session_end(name):
    p = players[name]
    now = time.time()
    session_length = round(now - p["session_start"], 1)
    with open(session_log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([round(now, 1), name, p["action_count"], 0.0, session_length, "", ENGINE_MODE, "session_end"])
    print(f"{name:<12} left -> session_length: {session_length}s logged")

def maybe_trigger_event(name, score):
    if ENGINE_MODE == "static":
        return

    p = players[name]
    now = time.time()
    if now - p["last_event_time"] < COOLDOWN_SECONDS:
        return

    if ENGINE_MODE == "rules":
        decision = decide_with_rules(name, score)
    else:
        decision = decide_with_ml(name)

    log_to_csv(name, score, decision)

    if decision == "reward":
        result = send_command(f"give {name} diamond 3")
        show_popup(name, "Reward!", "You received 3 diamonds", color="green", sound="entity.experience_orb.pickup")
        print(f"   [REWARD] {name} -> {result}")
        p["last_event_time"] = now
    elif decision == "reward_tiered":
        result = send_command(f"give {name} golden_apple 1")
        show_popup(name, "Big Reward!", "You received a golden apple", color="gold", sound="entity.player.levelup")
        print(f"   [REWARD_TIERED] {name} -> {result}")
        p["last_event_time"] = now
    elif decision == "challenge_mild":
        result = send_command(f"execute at {name} run summon minecraft:zombie ~2 ~ ~2")
        show_popup(name, "Challenge!", "A threat has appeared nearby", color="red", sound="entity.wither.spawn")
        print(f"   [CHALLENGE_MILD] {name} -> {result}")
        p["last_event_time"] = now
    elif decision == "challenge_hard":
        result = send_command(f"execute at {name} run summon minecraft:pillager ~2 ~ ~2")
        send_command(f"execute at {name} run summon minecraft:vindicator ~-2 ~ ~-2")
        show_popup(name, "Challenge!", "A serious threat has appeared", color="dark_red", sound="entity.ravager.roar")
        print(f"   [CHALLENGE_HARD] {name} -> {result}")
        p["last_event_time"] = now
    elif decision == "mercy":
        send_command(f"effect give {name} minecraft:regeneration 15 1")
        send_command(f"effect give {name} minecraft:resistance 15 1")
        show_popup(name, "Taking it easy", "Here's something to help you recover", color="aqua", sound="entity.player.levelup")
        print(f"   [MERCY] {name} -> regeneration + resistance applied")
        p["last_event_time"] = now

IDLE_CHECK_INTERVAL = 10
last_idle_check = time.time()

def check_idle_players():
    for name in list(players.keys()):
        score, _ = compute_score(name)
        maybe_trigger_event(name, score)

print(f"Watching for player activity... (engine: {ENGINE_MODE})\n")

with open(log_path, "r", encoding="utf-8") as f:
    f.seek(0, 2)
    while True:
        line = f.readline()
        if not line:
            time.sleep(1)
            if time.time() - last_idle_check >= IDLE_CHECK_INTERVAL:
                check_idle_players()
                last_idle_check = time.time()
            continue

        join_match = join_pattern.search(line)
        leave_match = leave_pattern.search(line)
        chat_match = chat_pattern.search(line)
        death_match = death_pattern.search(line)
        advancement_match = advancement_pattern.search(line)

        if leave_match:
            leave_name = leave_match.group(1)
            if leave_name in players:
                log_session_end(leave_name)
                del players[leave_name]

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