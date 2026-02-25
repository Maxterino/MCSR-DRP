# 🎮 MCSR Discord Rich Presence Tracker

> Show your Minecraft speedrun progress in real-time on your Discord profile — with custom images for each split!

![Discord RPC Preview](docs/preview.png)

When you're running Minecraft with the **SpeedRunIGT** mod, this program watches your run in real-time and updates your Discord status to show exactly what stage you're at:

| Split | Discord shows |
|-------|--------------|
| Just started | 🌳 Starting a new run |
| Entered Nether | 🔥 Entered the Nether |
| Bastion found | 🏰 In Bastion Remnant |
| Fortress found | 🏯 In Nether Fortress |
| Portal built | 🟪 Built First Portal |
| Stronghold | 👁 Locating Stronghold |
| End entered | 🌑 Entered the End |
| Dragon killed | 🏁 Run Complete! |

---

## 📋 Requirements

- **Python 3.9+** — [Download](https://www.python.org/downloads/) (check "Add to PATH" on Windows!)
- **Discord** — desktop app open and logged in
- **SpeedRunIGT mod** — installed in Minecraft (see [SpeedRunIGT](https://redlime.github.io/SpeedRunIGT/))
- **Your own Discord Application** — free, takes 2 minutes (see Step 2 below)

---

## 🚀 Quick Start

### Step 1 — Download this project

**Option A — Using Git:**
```bash
git clone https://github.com/YOUR_USERNAME/mcsr-discord-rpc.git
cd mcsr-discord-rpc
```

**Option B — Download ZIP:**
1. Click the green **Code** button on GitHub
2. Click **Download ZIP**
3. Extract to a folder you'll remember (e.g. `C:\mcsr-discord-rpc`)

---

### Step 2 — Create a Discord Application (one-time setup)

This gives you a Client ID so Discord knows to show your custom activity.

1. Go to **https://discord.com/developers/applications**
2. Click **"New Application"**
3. Name it something like `"Minecraft Speedrun"` — this name shows in your Discord status
4. Click **Create**
5. On the left sidebar click **"General Information"**
6. Copy the **Application ID** (a long number like `1234567890123456789`)

#### 2b — Upload the Rich Presence images

This step adds the images that appear next to your Discord status.

1. In your Discord Application, click **"Rich Presence"** on the left sidebar
2. Scroll down to **"Rich Presence Assets"** and click **"Add Image(s)"**
3. Upload images and name them **exactly** as listed below:

| Image file name (key) | What it shows |
|-----------------------|---------------|
| `overworld` | Main large image when starting run |
| `grass_block` | Small icon when starting |
| `nether` | Large image when in Nether |
| `nether_portal` | Small icon for nether enter |
| `bastion` | Small icon for bastion |
| `fortress` | Small icon for fortress |
| `obsidian` | Small icon for first portal |
| `stronghold` | Large image for stronghold phase |
| `ender_eye` | Small icon for stronghold |
| `end` | Large image for The End |
| `end_portal` | Small icon for end portal |
| `credits` | Large image for finished run |
| `dragon_egg` | Small icon for finished run |

> 💡 **Tip:** You can use any 512x512 PNG images you like! Search for Minecraft block/item textures online, or use screenshots. The key names above must match exactly.

---

### Step 3 — Configure the tracker

Open `config.ini` in a text editor and paste your **Application ID**:

```ini
[discord]
client_id = 1234567890123456789   ← paste YOUR number here
```

If Minecraft is not in the default location, also set:

```ini
[minecraft]
# Windows example:
mc_dir = C:\Users\YourName\AppData\Roaming\.minecraft

# Mac example:
mc_dir = /Users/YourName/Library/Application Support/minecraft
```

---

### Step 4 — Install Python dependencies

Open a terminal / command prompt in the project folder and run:

```bash
pip install -r requirements.txt
```

Or just double-click **`start.bat`** on Windows — it installs everything automatically!

---

### Step 5 — Run the tracker

**Windows:** Double-click `start.bat`

**Mac / Linux:**
```bash
chmod +x start.sh
./start.sh
```

**Or manually:**
```bash
python main.py
```

You should see:
```
══════════════════════════════════════════════════
  MCSR Discord Rich Presence Tracker
══════════════════════════════════════════════════
📁 Minecraft directory: C:\Users\...\AppData\Roaming\.minecraft
✅ Found SpeedRunIGT: ...\.minecraft\speedrunigt\latest_world
✅ Connected to Discord RPC
👀 Watching: ...
🚀 Tracker running! Open Minecraft with SpeedRunIGT to begin.
```

---

## 🧪 Testing Without Minecraft

You can test your Discord integration without opening Minecraft using the split simulator:

**Terminal 1 — Start the tracker pointing at a test directory:**
```bash
python main.py --mc-dir /tmp/mcsr_rpc_test
```

**Terminal 2 — Run the split simulator:**
```bash
python test_splits.py
```

The simulator will walk through all 7 splits with realistic delays. Watch your Discord profile update in real-time!

To run the simulation faster:
```bash
python test_splits.py --speed 3    # 3x faster
```

---

## ⚙️ Advanced Options

```
python main.py --help

  --mc-dir PATH      Path to .minecraft (auto-detected if not set)
  --client-id ID     Discord Application Client ID
  --debug            Verbose logging
```

---

## 🗂 How It Works

```
Minecraft + SpeedRunIGT mod
         │
         ▼
  .minecraft/speedrunigt/latest_world   ← JSON file updated live
         │
         ▼
  main.py (watchdog + poll)
  ├── Reads JSON file every ~2 seconds
  ├── Detects current split (nether, bastion, etc.)
  └── Calls pypresence to update Discord via IPC socket
         │
         ▼
  Discord Rich Presence (what your friends see)
```

SpeedRunIGT writes a `latest_world` JSON to `.minecraft/speedrunigt/` that looks like this:

```json
{
  "nether": 145234,
  "bastion": 198000,
  "fortress": null,
  "first_portal": null,
  "stronghold": null,
  "end": null,
  "finish": null
}
```

The tracker reads this and maps it to a Discord status. `null` means not reached yet.

---

## 📁 File Structure

```
mcsr-discord-rpc/
├── main.py           ← Main tracker application
├── test_splits.py    ← Run simulator for testing
├── config.ini        ← Your settings (Client ID, mc path)
├── requirements.txt  ← Python dependencies
├── start.bat         ← Windows one-click launcher
├── start.sh          ← Mac/Linux launcher
├── .gitignore
├── README.md
└── docs/
    └── preview.png   ← (add your own screenshot here)
```

---

## 🐛 Troubleshooting

### "Discord not running or connection failed"
→ Make sure the **Discord desktop app** is open (not just the browser). The RPC only works with the desktop app.

### "SpeedRunIGT latest_world not found"
→ Make sure you have the **SpeedRunIGT mod** installed and have started at least one world. The file is created on first use.
→ If using MultiMC or Prism Launcher, try passing your instance's `.minecraft` folder with `--mc-dir`.

### Status shows but images are blank
→ Images take a few minutes to process after uploading to Discord Developer Portal. Wait 5-10 minutes.
→ Double-check that image key names in Discord exactly match what's in `main.py`.

### Nothing happens when I enter the Nether
→ Check that SpeedRunIGT is tracking your run (you should see the timer on screen).
→ Look at the log output — is the file being read? Try `--debug` for more info.

---

## 🌐 Publishing to GitHub

### First time setup

```bash
# In the project folder:
git init
git add .
git commit -m "Initial commit: MCSR Discord RPC tracker"

# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/mcsr-discord-rpc.git
git branch -M main
git push -u origin main
```

### Recommended GitHub repo settings

1. **Add a description:** `Discord Rich Presence for Minecraft speedrunning — shows split progress in real-time`
2. **Add topics/tags:** `minecraft`, `speedrun`, `discord-rpc`, `mcsr`, `python`, `rich-presence`
3. **Create a Release:** Go to Releases → New Release → Upload a zip of the project so users can download easily without Git
4. **Add a screenshot:** Take a screenshot of your Discord status with the images showing and add it to `docs/preview.png` — put it in the README!

### Keeping it updated

```bash
git add .
git commit -m "Description of what changed"
git push
```

---

## 🙏 Credits & Related Projects

- [SpeedRunIGT](https://redlime.github.io/SpeedRunIGT/) — The Minecraft mod that generates the split data this tracker reads
- [PaceMan.gg](https://paceman.gg) — Public real-time speedrun pace tracker
- [PaceMan-Tracker](https://github.com/PaceMan-MCSR/PaceMan-Tracker) — Official PaceMan tracker (uploads to leaderboard)
- [pypresence](https://github.com/qwertyquerty/pypresence) — Python Discord RPC library
- [MCSR Community](https://discord.gg/mcspeedrun) — Join the speedrunning Discord!

---

## 📜 License

MIT License — free to use, modify, and share. See [LICENSE](LICENSE) for details.
