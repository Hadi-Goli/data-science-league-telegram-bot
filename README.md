# Data Science League Telegram Bot

A robust, asynchronous Telegram bot designed for managing Data Science competitions. It evaluates student submissions (CSV) using **RMSE**, maintains a real-time leaderboard, and provides a full-featured admin panel.

## 🚀 Features

### For Participants
- **Self-Claim Authentication**: Users authenticate by providing their full name, matched against an encrypted/database-backed whitelist.
- **CSV Submission**: Participants upload `.csv` files. The bot processes them in memory (via `io.BytesIO`), calculates RMSE against a ground-truth `solution.csv`, and provides instant feedback.
- **Dynamic Leaderboard**: View the top 10 rankings with `/leaderboard`.
- **Personal Stats**: Check current rank and best score with `/rank`.
- **Persian UI**: All user interactions are in Persian (Farsi).

### For Administrators
- **Admin Panel**: Accessible via `/admin` for authorized users.
- **User Management**: Add or remove names from the whitelist dynamically.
- **Data Export**: Dump the entire database of users and submissions to a CSV/Excel file.
- **Competition Control**: Toggle a "Freeze" flag to stop accepting new submissions.
- **Global Broadcast**: Send messages to all registered users simultaneously.

## 🛠 Tech Stack

- **Framework**: [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) (v20+, Async)
- **Database**: PostgreSQL with [SQLAlchemy](https://www.sqlalchemy.org/) (Async) & [asyncpg](https://github.com/MagicStack/asyncpg)
- **Data Processing**: [Pandas](https://pandas.pydata.org/) & [Scikit-learn](https://scikit-learn.org/)
- **Deployment**: Optimized for ephemeral filesystems (e.g., Railway, Heroku) using in-memory processing.

## ⚙️ Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/data-science-league-bot.git
   cd data-science-league-bot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file based on `.env.example`:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname
   FIRST_ADMIN_ID=your_telegram_user_id
   ```

4. **Add Ground Truth**:
   Place your `solution.csv` in the project root. It should contain at least one numeric target column (e.g., `G3`).

5. **Run the bot**:
   ```bash
   python main.py
   ```

## 📜 Commands

- `/start` - Begin authentication flow.
- `/help` - Show help message and command list.
- `/leaderboard` - Show top 10 performers.
- `/rank` - Show your personal best and rank.
- `/admin` - Access the management panel (Admin only).

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.