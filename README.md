# 🕹️ Deltarune Countdown Discord Bot

A simple Discord bot that counts down to the release of **DELTARUNE** on Steam — and celebrates when it's finally out!  
It updates a channel name with the number of days remaining and checks Steam to detect when the game is officially released.

> 🗓 Release Date: **June 5, 2025**  
> 🎮 Steam: [`DELTARUNE`](https://store.steampowered.com/app/1671210/DELTARUNE/)

---

## ✨ Features

- ⏳ Updates a Discord channel name to show how many days are left
- 📢 Sends a hype message the day before launch
- 🚨 Announces when the game is officially released
- 🔄 Checks Steam API regularly to detect release
- 💾 Saves state between restarts (so no duplicate announcements)

---

## 🚀 Deployment

This bot is designed to work with [Nixpacks](https://nixpacks.com/) and runs on most modern cloud platforms like Railway, Fly.io, or Render.

### Prerequisites

- Python 3.11+
- A Discord bot token
- A channel ID where the bot has permission to edit the name

### 🛠 Setup

1. Clone the repository:

```bash
git clone https://github.com/mishl-dev/deltarune-countdown-bot.git
cd deltarune-countdown-bot
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory:

```env
DISCORD_TOKEN=your-bot-token-here
COUNTDOWN_CHANNEL_ID=your-channel-id-here
```

4. Run the bot:

```bash
python bot.py
```

---

## 📦 Nixpacks Support

If you're deploying with Nixpacks, this project includes a `nixpacks.toml`. No need to manage Docker or custom build scripts.

---


## 🧠 Credits

Made with 💙 by [@mishl-dev](https://github.com/mishl-dev)  
Powered by Discord.py, Steam API, and fan hype.

---

## 📝 License
MIT — do whatever, just don't sue me.
