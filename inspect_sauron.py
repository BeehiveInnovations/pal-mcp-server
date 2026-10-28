import os
sauron_dir = "/home/kali/tools/sauron-work/sauron"
print("--- Sauron files ---")
for root, dirs, files in os.walk(sauron_dir):
    # skip .git
    if '.git' in dirs:
        dirs.remove('.git')
    for f in files:
        rel = os.path.relpath(os.path.join(root, f), sauron_dir)
        print(rel)
