"""
Supreme Gmail Bot â€” v4.0
Features: Anti-detect 1.0 / 2.0 / 3.0, Admin 2FA (TOTP),
          Multi-language BN/EN, USDT, Bot ON/OFF,
          24/7 HTTP health server, Crash-proof WAL SQLite
"""

import sqlite3, os, re, fcntl, random, string, time, threading, imaplib, ssl, smtplib
import pyotp
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  CONFIG
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
BOT_TOKEN = os.environ.get("8600286616:AAE2TeKzRhLfpXyeHmijIriqUnq1vclJevI", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7835608287"))
ADMIN_2FA_SECRET = (
    "ODT4NEP2UB7QIDDFSLJ7S23M3F5PERM7"  # your Google Auth secret (uppercase, no spaces)
)
DB_FILE = "supreme_gmail_bot.db"

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  SINGLE-INSTANCE LOCK
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
_lock_fh = open("/tmp/supreme_gmail_bot.lock", "w")
print("ðŸ”’ à¦ªà§à¦°à¦¨à§‹ instance à¦¬à¦¨à§à¦§ à¦¹à¦“à¦¯à¦¼à¦¾à¦° à¦…à¦ªà§‡à¦•à§à¦·à¦¾ à¦•à¦°à¦›à¦¿...")
fcntl.flock(_lock_fh, fcntl.LOCK_EX)
_lock_fh.write(str(os.getpid()))
_lock_fh.flush()
print("ðŸ”’ Lock à¦¨à§‡à¦“à¦¯à¦¼à¦¾ à¦¹à¦¯à¦¼à§‡à¦›à§‡ â€” à¦à¦•à¦Ÿà¦¿à¦®à¦¾à¦¤à§à¦° instance à¦šà¦²à¦›à§‡")
time.sleep(3)

(bot = telebot.TeleBot("8600286616:AAE2TeKzRhLfpXyeHmijIriqUnq1vclJevI", threaded=True, num_threads=8), threaded=True, num_threads=8)
user_states = {}
state_lock = threading.Lock()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  24/7 HTTP HEALTH SERVER  (ping via UptimeRobot)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class _PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Supreme Gmail Bot is alive! ")

    def log_message(self, *a):
        pass  # suppress access logs


def _start_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        srv = HTTPServer(("0.0.0.0", port), _PingHandler)
        print(f"ðŸŒ Health server on port {port}")
        srv.serve_forever()
    except Exception as e:
        print(f"âš ï¸ Health server error: {e}")


threading.Thread(target=_start_health_server, daemon=True).start()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  THREAD-LOCAL DB  (WAL mode â€” safe for 100k users)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
_tl = threading.local()


def db():
    if not hasattr(_tl, "conn") or _tl.conn is None:
        c = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=15)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-32000")
        _tl.conn = c
    return _tl.conn


def run(sql, params=(), fetch="none"):
    conn = db()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return cur.lastrowid
    except sqlite3.OperationalError as e:
        conn.rollback()
        raise e


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  DATABASE INIT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def init_db():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            balance     REAL    DEFAULT 0.0,
            referred_by INTEGER DEFAULT NULL,
            language    TEXT    DEFAULT 'bn'
        );
        CREATE TABLE IF NOT EXISTS submissions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            username      TEXT,
            gmail_type    TEXT,
            email_user    TEXT,
            gmail_data    TEXT,
            recovery_mail TEXT,
            two_fa        TEXT,
            status        TEXT DEFAULT 'Pending',
            is_valid      TEXT DEFAULT 'Not Checked'
        );
        CREATE TABLE IF NOT EXISTS withdrawals (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            binance_id TEXT,
            amount     REAL,
            status     TEXT DEFAULT 'Pending'
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sub_email  ON submissions(email_user);
        CREATE INDEX IF NOT EXISTS idx_sub_uid    ON submissions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sub_status ON submissions(status);
        CREATE INDEX IF NOT EXISTS idx_wd_status  ON withdrawals(status);
    """)
    c.commit()

    # Safe column migrations
    for tbl, col, defn in [
        ("users", "referred_by", "INTEGER DEFAULT NULL"),
        ("users", "language", "TEXT DEFAULT 'bn'"),
    ]:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
            c.commit()
        except:
            pass

    defaults = [
        ("price_new", "5.00"),
        ("price_old", "10.00"),
        ("req_2fa_new", "0"),
        ("req_2fa_old", "1"),
        ("req_recovery_new", "0"),
        ("req_recovery_old", "1"),
        ("auto_checker", "0"),
        ("antidect2", "0"),
        ("min_withdrawal", "10.00"),
        ("refer_commission", "10.0"),
        ("bot_enabled", "1"),
        ("currency", "USDT"),
        ("admin_2fa", "0"),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))

    # Migrate old combined keys
    for old, n, o in [
        ("req_2fa", "req_2fa_new", "req_2fa_old"),
        ("req_recovery", "req_recovery_new", "req_recovery_old"),
    ]:
        row = c.execute("SELECT value FROM settings WHERE key=?", (old,)).fetchone()
        if row:
            for k in (n, o):
                c.execute(
                    "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                    (k, row[0]),
                )
            c.execute("DELETE FROM settings WHERE key=?", (old,))
    c.commit()


init_db()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  TRANSLATIONS  (BN / EN)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
T = {
    "bn": {
        # Menu buttons
        "btn_sell_new": "ðŸ†• à¦¨à¦¤à§à¦¨ Gmail à¦¬à§‡à¦šà§à¦¨",
        "btn_sell_old": "ðŸ‘´ à¦ªà§à¦°à¦¨à§‹ Gmail à¦¬à§‡à¦šà§à¦¨",
        "btn_balance": "ðŸ’° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸",
        "btn_withdraw": "ðŸ§ à¦‰à¦¤à§à¦¤à§‹à¦²à¦¨",
        "btn_history": "ðŸ“‹ à¦†à¦®à¦¾à¦° à¦¸à¦¾à¦¬à¦®à¦¿à¦¶à¦¨",
        "btn_refer": "ðŸ‘¥ Refer & Earn",
        "btn_language": "ðŸŒ à¦­à¦¾à¦·à¦¾ à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨",
        "btn_cancel": "âŒ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à§à¦¨",
        # Welcome
        "welcome": "ðŸŒŸ *Supreme Gmail Bot-à¦ à¦¸à§à¦¬à¦¾à¦—à¦¤à¦®!*",
        "price_list": "â”â”â” ðŸ’µ à¦®à§‚à¦²à§à¦¯ à¦¤à¦¾à¦²à¦¿à¦•à¦¾ â”â”â”",
        "refer_line": "ðŸ‘¥ Refer à¦•à¦°à§à¦¨ â€” à¦ªà§à¦°à¦¤à¦¿ Approval-à¦ *{r}%* Commission!",
        "start_menu": "â¬‡ï¸ à¦¨à¦¿à¦šà§‡à¦° à¦®à§‡à¦¨à§ à¦¥à§‡à¦•à§‡ à¦¬à§‡à¦›à§‡ à¦¨à¦¿à¦¨:",
        "maintenance": "ðŸ”§ *Bot à¦¸à¦¾à¦®à¦¯à¦¼à¦¿à¦•à¦­à¦¾à¦¬à§‡ à¦¬à¦¨à§à¦§à¥¤*\nà¦¶à§€à¦˜à§à¦°à¦‡ à¦šà¦¾à¦²à§ à¦¹à¦¬à§‡à¥¤",
        "cancelled": "âœ… à¦¬à¦¾à¦¤à¦¿à¦² à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤",
        "menu_hint": "ðŸ‘‡ à¦®à§‡à¦¨à§ à¦¥à§‡à¦•à§‡ à¦¬à¦¿à¦•à¦²à§à¦ª à¦¬à§‡à¦›à§‡ à¦¨à¦¿à¦¨à¥¤",
        # Balance
        "balance_title": "ðŸ’° à¦†à¦ªà¦¨à¦¾à¦° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸",
        "balance_cur": "ðŸ’µ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸",
        "referrals": "ðŸ‘¥ à¦†à¦ªà¦¨à¦¾à¦° Referral à¦¸à¦‚à¦–à§à¦¯à¦¾",
        "balance_note": "Gmail Approve à¦¹à¦²à§‡ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¯à§‹à¦— à¦¹à¦¬à§‡à¥¤",
        # History
        "sub_history": "ðŸ“‹ à¦¸à¦¾à¦®à§à¦ªà§à¦°à¦¤à¦¿à¦• à¦¸à¦¾à¦¬à¦®à¦¿à¦¶à¦¨ (à¦¸à¦°à§à¦¬à¦¶à§‡à¦· à§§à§¦à¦Ÿà¦¿):",
        "no_subs": "ðŸ“­ à¦†à¦ªà¦¨à¦¾à¦° à¦•à§‹à¦¨à§‹ à¦¸à¦¾à¦¬à¦®à¦¿à¦¶à¦¨ à¦¨à§‡à¦‡à¥¤",
        # Refer
        "refer_title": "ðŸ‘¥ Refer & Earn",
        "refer_comm": "ðŸ’¸ Commission à¦¹à¦¾à¦°",
        "refer_count": "ðŸ“Š à¦†à¦ªà¦¨à¦¾à¦° à¦®à§‹à¦Ÿ Referral",
        "refer_link": "ðŸ”— à¦†à¦ªà¦¨à¦¾à¦° Referral Link",
        "refer_note": "ðŸ“¢ à¦à¦‡ link à¦¬à¦¨à§à¦§à§à¦¦à§‡à¦° à¦ªà¦¾à¦ à¦¾à¦¨ â€” à¦¤à¦¾à¦¦à§‡à¦° Gmail Approved à¦¹à¦²à§‡ commission à¦ªà¦¾à¦¬à§‡à¦¨! ðŸŽ",
        # New Gmail
        "new_gen_title": "à¦¨à¦¤à§à¦¨ Gmail Generate à¦¹à¦¯à¦¼à§‡à¦›à§‡",
        "new_gen_price": "ðŸ’µ à¦®à§‚à¦²à§à¦¯",
        "new_gen_copy": "ðŸ‘† Copy à¦•à¦°à§à¦¨, à¦¤à¦¾à¦°à¦ªà¦° Submit à¦•à¦°à§à¦¨à¥¤",
        # Old Gmail
        "old_title": "à¦ªà§à¦°à¦¨à§‹ Gmail à¦¸à¦¾à¦¬à¦®à¦¿à¦Ÿ",
        "old_step1_hdr": "à¦§à¦¾à¦ª à§§ / à¦‡à¦®à§‡à¦‡à¦² à¦ à¦¿à¦•à¦¾à¦¨à¦¾ à¦¦à¦¿à¦¨",
        "old_step1_ok": "âœ… à¦¸à¦ à¦¿à¦• à¦‰à¦¦à¦¾à¦¹à¦°à¦£",
        "old_step1_bad": "âŒ à¦­à§à¦² à¦‰à¦¦à¦¾à¦¹à¦°à¦£",
        "old_gmail_only": "âŒ *à¦¶à§à¦§à§à¦®à¦¾à¦¤à§à¦° @gmail.com à¦ à¦¿à¦•à¦¾à¦¨à¦¾ à¦¦à¦¿à¦¨!*\nâœ… à¦¸à¦ à¦¿à¦•: `yourname@gmail.com`\n\nðŸ”„ à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨:",
        "old_step2": "ðŸ“§ `{email}` à¦¸à¦‚à¦°à¦•à§à¦·à¦¿à¦¤ âœ…\n\nðŸ”‘ *à¦§à¦¾à¦ª à§¨ / Password à¦¦à¦¿à¦¨:*",
        "old_pass_short": "âŒ Password à¦•à¦®à¦ªà¦•à§à¦·à§‡ à§¬ à¦…à¦•à§à¦·à¦°à§‡à¦° à¦¹à¦¤à§‡ à¦¹à¦¬à§‡à¥¤",
        "pass_saved": "ðŸ”‘ Password à¦¸à¦‚à¦°à¦•à§à¦·à¦¿à¦¤ âœ…",
        "old_recovery": "ðŸ“§ Recovery Email à¦¦à¦¿à¦¨\n_(Gmail, Outlook, Hotmail, Tempmail â€” à¦¸à¦¬ à¦šà¦²à¦¬à§‡)_\n_à¦¨à¦¾ à¦¥à¦¾à¦•à¦²à§‡ `none` à¦²à¦¿à¦–à§à¦¨_",
        "old_2fa": "ðŸ” 2FA à¦•à§‹à¦¡ à¦¦à¦¿à¦¨\n_à¦¨à¦¾ à¦¥à¦¾à¦•à¦²à§‡ `none` à¦²à¦¿à¦–à§à¦¨_",
        "bad_recovery": "âŒ *à¦¸à¦ à¦¿à¦• email à¦¦à¦¿à¦¨à¥¤*\n_(à¦¯à§‡à¦•à§‹à¦¨à§‹ email à¦…à¦¥à¦¬à¦¾ `none`)_",
        # Review
        "review_title": "à¦¸à¦¾à¦¬à¦®à¦¿à¦¶à¦¨ à¦°à¦¿à¦­à¦¿à¦‰",
        "review_confirm": "à¦¨à¦¿à¦¶à§à¦šà¦¿à¦¤ à¦¹à¦²à§‡ *Confirm* à¦šà¦¾à¦ªà§à¦¨:",
        "sub_success": "à¦¸à¦¾à¦¬à¦®à¦¿à¦¶à¦¨ à¦¸à¦«à¦² à¦¹à¦¯à¦¼à§‡à¦›à§‡",
        "sub_pending": "Approve à¦¹à¦²à§‡ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¯à§‹à¦— à¦¹à¦¬à§‡à¥¤",
        "approved_msg": "ðŸŽ‰ à¦¸à¦¾à¦¬à¦®à¦¿à¦¶à¦¨ ID `{id}` *Approved!*\nðŸ’° *{price} {cur}* à¦¯à§‹à¦— à¦¹à¦¯à¦¼à§‡à¦›à§‡!\nðŸ’³ à¦®à§‹à¦Ÿ: *{bal} {cur}*",
        "rejected_msg": "ðŸ˜” à¦¸à¦¾à¦¬à¦®à¦¿à¦¶à¦¨ ID `{id}` *Rejected* à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤",
        # Withdrawal
        "wd_title": "à¦‰à¦¤à§à¦¤à§‹à¦²à¦¨",
        "wd_low_bal": "âŒ *à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦…à¦ªà¦°à§à¦¯à¦¾à¦ªà§à¦¤*\n\nðŸ’° à¦†à¦ªà¦¨à¦¾à¦°: *{bal} {cur}*\nðŸ“Œ à¦¸à¦°à§à¦¬à¦¨à¦¿à¦®à§à¦¨: *{min} {cur}*",
        "wd_step1": "ðŸ¦ *à¦§à¦¾à¦ª à§§ / Binance ID à¦¦à¦¿à¦¨:*",
        "wd_bid_saved": "ðŸ¦ Binance ID à¦¸à¦‚à¦°à¦•à§à¦·à¦¿à¦¤ âœ…",
        "wd_step2": "ðŸ’µ *à¦§à¦¾à¦ª à§¨ / à¦ªà¦°à¦¿à¦®à¦¾à¦£ à¦¦à¦¿à¦¨*\nðŸ’° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: *{bal} {cur}*\nðŸ“Œ à¦¸à¦°à§à¦¬à¦¨à¦¿à¦®à§à¦¨: *{min} {cur}*",
        "wd_invalid_amt": "âŒ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦¦à¦¿à¦¨, à¦¯à§‡à¦®à¦¨: `5.00`",
        "wd_too_low": "âŒ à¦¸à¦°à§à¦¬à¦¨à¦¿à¦®à§à¦¨ à¦‰à¦¤à§à¦¤à§‹à¦²à¦¨: *{min} {cur}*",
        "wd_over_bal": "âŒ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦®à¦¾à¦¤à§à¦° *{bal} {cur}*",
        "wd_bad_id": "âŒ à¦¸à¦ à¦¿à¦• Binance ID à¦¦à¦¿à¦¨à¥¤",
        "wd_success": "à¦‰à¦¤à§à¦¤à§‹à¦²à¦¨à§‡à¦° à¦†à¦¬à§‡à¦¦à¦¨ à¦¸à¦«à¦²",
        "wd_approved": "ðŸ’¸ à¦‰à¦¤à§à¦¤à§‹à¦²à¦¨ ID `{id}` *Approved!*\nðŸ’° *{amt} {cur}* à¦ªà¦¾à¦ à¦¾à¦¨à§‹ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤",
        "wd_rejected": "ðŸ˜” à¦‰à¦¤à§à¦¤à§‹à¦²à¦¨ ID `{id}` *Rejected*à¥¤\nðŸ’° *{amt} {cur}* à¦«à§‡à¦°à¦¤ à¦¦à§‡à¦“à¦¯à¦¼à¦¾ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤",
        # Anti-detect
        "dup_email": "âŒ *à¦à¦‡ à¦œà¦¿à¦®à§‡à¦‡à¦²à¦Ÿà¦¿ à¦‡à¦¤à¦¿à¦®à¦§à§à¦¯à§‡ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦¸à¦¿à¦¸à§à¦Ÿà§‡à¦®à§‡ à¦¸à¦¾à¦¬à¦®à¦¿à¦Ÿ à¦•à¦°à¦¾ à¦¹à¦¯à¦¼à§‡à¦›à§‡!*\nà¦¦à¦¯à¦¼à¦¾ à¦•à¦°à§‡ à¦à¦•à¦Ÿà¦¿ à¦«à§à¦°à§‡à¦¶ à¦œà¦¿à¦®à§‡à¦‡à¦² à¦¦à¦¿à¦¨à¥¤",
        "gmail_no_exist": "âš ï¸ *à¦à¦‡ Gmail Account à¦ªà¦¾à¦“à¦¯à¦¼à¦¾ à¦¯à¦¾à¦¯à¦¼à¦¨à¦¿!*\nà¦¶à§à¦§à§à¦®à¦¾à¦¤à§à¦° existing Gmail à¦¸à¦¾à¦¬à¦®à¦¿à¦Ÿ à¦•à¦°à§à¦¨à¥¤",
        # Referral commission
        "ref_commission": "ðŸŽ *Referral Commission!*\nðŸ’° *{amt} {cur}* à¦¯à§‹à¦— à¦¹à¦¯à¦¼à§‡à¦›à§‡!",
        # Language
        "lang_select": "ðŸŒ à¦­à¦¾à¦·à¦¾ à¦¬à§‡à¦›à§‡ à¦¨à¦¿à¦¨:",
        "lang_set_bn": "âœ… à¦¬à¦¾à¦‚à¦²à¦¾ à¦¸à§‡à¦Ÿ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤",
        "lang_set_en": "âœ… English has been set.",
        # Admin 2FA
        "adm_2fa_prompt": "ðŸ” Admin Panel-à¦ à¦ªà§à¦°à¦¬à§‡à¦¶à§‡à¦° à¦œà¦¨à§à¦¯ *2FA à¦•à§‹à¦¡* à¦¦à¦¿à¦¨:",
        "adm_2fa_wrong": "âŒ *à¦­à§à¦² 2FA à¦•à§‹à¦¡!* à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨à¥¤",
        "adm_2fa_ok": "âœ… 2FA à¦¯à¦¾à¦šà¦¾à¦‡ à¦¸à¦«à¦²!",
    },
    "en": {
        # Menu buttons (match Bengali exactly â€” routing works on text match)
        "btn_sell_new": "ðŸ†• à¦¨à¦¤à§à¦¨ Gmail à¦¬à§‡à¦šà§à¦¨",
        "btn_sell_old": "ðŸ‘´ à¦ªà§à¦°à¦¨à§‹ Gmail à¦¬à§‡à¦šà§à¦¨",
        "btn_balance": "ðŸ’° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸",
        "btn_withdraw": "ðŸ§ à¦‰à¦¤à§à¦¤à§‹à¦²à¦¨",
        "btn_history": "ðŸ“‹ à¦†à¦®à¦¾à¦° à¦¸à¦¾à¦¬à¦®à¦¿à¦¶à¦¨",
        "btn_refer": "ðŸ‘¥ Refer & Earn",
        "btn_language": "ðŸŒ à¦­à¦¾à¦·à¦¾ à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨",
        "btn_cancel": "âŒ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à§à¦¨",
        # Welcome
        "welcome": "ðŸŒŸ *Welcome to Supreme Gmail Bot!*",
        "price_list": "â”â”â” ðŸ’µ Price List â”â”â”",
        "refer_line": "ðŸ‘¥ Refer friends â€” earn *{r}%* per Approval!",
        "start_menu": "â¬‡ï¸ Choose from the menu below:",
        "maintenance": "ðŸ”§ *Bot is temporarily offline.*\nWill be back soon.",
        "cancelled": "âœ… Cancelled.",
        "menu_hint": "ðŸ‘‡ Please select from the menu.",
        # Balance
        "balance_title": "ðŸ’° Your Balance",
        "balance_cur": "ðŸ’µ Current Balance",
        "referrals": "ðŸ‘¥ Total Referrals",
        "balance_note": "Balance is added when Gmail is Approved.",
        # History
        "sub_history": "ðŸ“‹ Recent Submissions (last 10):",
        "no_subs": "ðŸ“­ You have no submissions yet.",
        # Refer
        "refer_title": "ðŸ‘¥ Refer & Earn",
        "refer_comm": "ðŸ’¸ Commission Rate",
        "refer_count": "ðŸ“Š Your Total Referrals",
        "refer_link": "ðŸ”— Your Referral Link",
        "refer_note": "ðŸ“¢ Share this link â€” earn commission when their Gmail gets Approved! ðŸŽ",
        # New Gmail
        "new_gen_title": "New Gmail Generated",
        "new_gen_price": "ðŸ’µ Price",
        "new_gen_copy": "ðŸ‘† Copy credentials, then tap Submit.",
        # Old Gmail
        "old_title": "Old Gmail Submit",
        "old_step1_hdr": "Step 1 / Enter Gmail address",
        "old_step1_ok": "âœ… Correct example",
        "old_step1_bad": "âŒ Wrong example",
        "old_gmail_only": "âŒ *Only @gmail.com addresses are accepted!*\nâœ… Correct: `yourname@gmail.com`\n\nðŸ”„ Try again:",
        "old_step2": "ðŸ“§ `{email}` saved âœ…\n\nðŸ”‘ *Step 2 / Enter Password:*",
        "old_pass_short": "âŒ Password must be at least 6 characters.",
        "pass_saved": "ðŸ”‘ Password saved âœ…",
        "old_recovery": "ðŸ“§ Enter Recovery Email\n_(Gmail, Outlook, Hotmail, Tempmail â€” all accepted)_\n_Type `none` if not available_",
        "old_2fa": "ðŸ” Enter 2FA code\n_Type `none` if not available_",
        "bad_recovery": "âŒ *Enter a valid email.*\n_(Any email format or `none`)_",
        # Review
        "review_title": "Submission Review",
        "review_confirm": "Tap *Confirm* to submit:",
        "sub_success": "Submission Successful",
        "sub_pending": "Balance will be added upon Approval.",
        "approved_msg": "ðŸŽ‰ Submission ID `{id}` *Approved!*\nðŸ’° *{price} {cur}* added!\nðŸ’³ Total: *{bal} {cur}*",
        "rejected_msg": "ðŸ˜” Submission ID `{id}` *Rejected*.",
        # Withdrawal
        "wd_title": "Withdrawal",
        "wd_low_bal": "âŒ *Insufficient Balance*\n\nðŸ’° Yours: *{bal} {cur}*\nðŸ“Œ Minimum: *{min} {cur}*",
        "wd_step1": "ðŸ¦ *Step 1 / Enter your Binance ID:*",
        "wd_bid_saved": "ðŸ¦ Binance ID saved âœ…",
        "wd_step2": "ðŸ’µ *Step 2 / Enter amount*\nðŸ’° Balance: *{bal} {cur}*\nðŸ“Œ Minimum: *{min} {cur}*",
        "wd_invalid_amt": "âŒ Enter a valid number, e.g. `5.00`",
        "wd_too_low": "âŒ Minimum withdrawal: *{min} {cur}*",
        "wd_over_bal": "âŒ Balance is only *{bal} {cur}*",
        "wd_bad_id": "âŒ Enter a valid Binance ID.",
        "wd_success": "Withdrawal Request Successful",
        "wd_approved": "ðŸ’¸ Withdrawal ID `{id}` *Approved!*\nðŸ’° *{amt} {cur}* has been sent.",
        "wd_rejected": "ðŸ˜” Withdrawal ID `{id}` *Rejected*.\nðŸ’° *{amt} {cur}* has been refunded.",
        # Anti-detect
        "dup_email": "âŒ *This Gmail has already been submitted to our system!*\nPlease submit a fresh Gmail.",
        "gmail_no_exist": "âš ï¸ *This Gmail Account does not exist!*\nOnly submit existing Gmail accounts.",
        # Referral commission
        "ref_commission": "ðŸŽ *Referral Commission!*\nðŸ’° *{amt} {cur}* added!",
        # Language
        "lang_select": "ðŸŒ à¦­à¦¾à¦·à¦¾ à¦¬à§‡à¦›à§‡ à¦¨à¦¿à¦¨ â€” Select Language:",
        "lang_set_bn": "âœ… à¦¬à¦¾à¦‚à¦²à¦¾ à¦¸à§‡à¦Ÿ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤",
        "lang_set_en": "âœ… English has been set.",
        # Admin 2FA
        "adm_2fa_prompt": "ðŸ” Enter *2FA code* to access Admin Panel:",
        "adm_2fa_wrong": "âŒ *Wrong 2FA code!* Try again.",
        "adm_2fa_ok": "âœ… 2FA verified!",
    },
}


def get_lang(uid):
    row = run("SELECT language FROM users WHERE user_id=?", (uid,), "one")
    if row and row[0] in T:
        return row[0]
    return "bn"


def tx(uid, key, **kw):
    lang = get_lang(uid)
    s = T[lang].get(key) or T["bn"].get(key, key)
    return s.format(**kw) if kw else s


def currency():
    row = run("SELECT value FROM settings WHERE key='currency'", fetch="one")
    return row[0] if row else "USDT"


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  SETTINGS / DB HELPERS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def gs(key):
    row = run("SELECT value FROM settings WHERE key=?", (key,), "one")
    return row[0] if row else None


def ss(key, value):
    run("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))


def get_balance(uid):
    row = run("SELECT balance FROM users WHERE user_id=?", (uid,), "one")
    return row[0] if row else 0.0


def add_balance(uid, amt):
    run("UPDATE")
