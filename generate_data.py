import random
import csv

rows = []

for _ in range(500):
       action_count = random.randint(0, 20)
       idle_time = random.uniform(0, 120)
       session_length = random.uniform(0, 1800)

       score = (action_count * 2) - (idle_time * 0.1)

       if score < 3:
           label = "reward"
       elif score > 15:
           label = "challenge"
       else:
           label = "none"

       rows.append([action_count, idle_time, session_length, score, label])

with open("training_data.csv", "w", newline="") as f:
       writer = csv.writer(f)
       writer.writerow(["action_count", "idle_time", "session_length", "score", "label"])
       writer.writerows(rows)

print("Generated 500 rows into training_data.csv")