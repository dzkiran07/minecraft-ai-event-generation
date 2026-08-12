import random
import csv

rows = []

for _ in range(500):
       action_count = random.randint(0, 20)
       idle_time = random.uniform(0, 120)
       session_length = random.uniform(0, 1800)

       score = (action_count * 2) - (idle_time * 0.1)

       if idle_time > 60:
           label = "reward"
       elif action_count >= 8 and idle_time < 15 and session_length > 60:
           label = "challenge"
       elif action_count >= 5 and idle_time < 30:
           label = "challenge" if session_length > 120 else "none"
       else:
           label = "none"

       rows.append([action_count, idle_time, session_length, score, label])

with open("training_data.csv", "w", newline="") as f:
       writer = csv.writer(f)
       writer.writerow(["action_count", "idle_time", "session_length", "score", "label"])
       writer.writerows(rows)

print("Generated 500 rows into training_data.csv")