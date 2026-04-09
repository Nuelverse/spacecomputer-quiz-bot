# bot.py
import asyncio
import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

import config
from ctrng import get_cosmic_random, cosmic_shuffle, cosmic_choice
from ai import generate_questions
from quiz import QuizSession
from knowledge_base import build_knowledge_base
from database import (
    init_db, save_questions, get_asked_questions, get_question_count,
    update_all_time_scores, get_all_time_leaderboard, get_player_stats,
)

active_sessions: dict[int, QuizSession] = {}

SEP = "━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOPIC_EMOJIS = {
    "ctrng": "🎲",
    "kms": "🔐",
    "orbital computing": "🛸",
    "spacecomputer architecture": "🏗️",
    "blockchain randomness": "⛓️",
    "general": "🌍",
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def esc(text: str) -> str:
    """Escape special MarkdownV2 characters in dynamic text."""
    chars = r'_*[]()~`>#+-=|{}.!'
    for ch in chars:
        text = text.replace(ch, f'\\{ch}')
    return text


def topic_emoji(topic: str) -> str:
    return TOPIC_EMOJIS.get(topic.lower(), "🛰️")


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def group_admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Returns True if the command should proceed.
    Blocks private chats and non-admins; auto-deletes both the user command
    and the error reply after AUTO_DELETE_DELAY seconds.
    """
    chat = update.effective_chat
    user_msg_id = update.message.message_id

    if chat.type == "private":
        sent = await update.message.reply_text(
            "⛔ _This command only works inside the SpaceComputer group chat\\._",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        _schedule(_auto_delete(chat.id, [user_msg_id, sent.message_id], context))
        return False

    if not await is_admin(update, context):
        sent = await update.message.reply_text(
            "⛔ _Only group admins can use this command\\._",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        _schedule(_auto_delete(chat.id, [user_msg_id, sent.message_id], context))
        return False

    # Admin passed — delete their command message too
    _schedule(_auto_delete(chat.id, [user_msg_id], context))
    return True


# Strong references to background tasks — prevents Python GC from killing them mid-run
_bg_tasks: set = set()


def _schedule(coro) -> asyncio.Task:
    """Create a background task and keep a strong reference so GC can't kill it."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return task


async def _delete_messages(chat_id: int, message_ids: list, context: ContextTypes.DEFAULT_TYPE):
    """Silently delete a list of messages, respecting rate limits."""
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass
        await asyncio.sleep(0.05)


async def _auto_delete(chat_id: int, message_ids: list, context: ContextTypes.DEFAULT_TYPE, delay: int = None):
    """Delete messages after a delay. Delay defaults to config.AUTO_DELETE_DELAY."""
    await asyncio.sleep(delay if delay is not None else config.AUTO_DELETE_DELAY)
    await _delete_messages(chat_id, message_ids, context)


async def _cleanup_session(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Pop session, cancel timer, delete all tracked round messages in background."""
    s = active_sessions.pop(chat_id, None)
    if not s:
        return
    if s.timer_task and not s.timer_task.done():
        s.timer_task.cancel()
    if s.bot_message_ids:
        _schedule(_delete_messages(chat_id, list(s.bot_message_ids), context))


async def _send_dm_or_warn(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    username: str,
    text: str,
):
    """Send text to user's DM. In groups, post a brief ack or a 'DM me first' warning."""
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
        return
    try:
        await context.bot.send_message(user_id, text, parse_mode=ParseMode.MARKDOWN_V2)
        sent = await update.message.reply_text(
            f"📬 _Sent to your DMs, @{username}\\!_",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        _schedule(_auto_delete(chat.id, [update.message.message_id, sent.message_id], context))
    except Exception:
        sent = await update.message.reply_text(
            f"⚠️ _@{username}, I can't DM you\\._\n"
            f"_Start me in private first, then try again\\._",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        _schedule(_auto_delete(chat.id, [update.message.message_id, sent.message_id], context))


# ─────────────────────────────────────────────
# MESSAGE BUILDERS
# ─────────────────────────────────────────────

def build_leaderboard_text(session: QuizSession) -> str:
    board = session.get_leaderboard()
    if not board:
        return "_No scores recorded\\._"
    medals = ["🥇", "🥈", "🥉"]
    q_played = session.questions_played
    text = f"📊 *FINAL LEADERBOARD*\n{SEP}\n"
    for i, player in enumerate(board[:10]):
        medal = medals[i] if i < 3 else f"{i+1}\\."
        text += f"{medal} @{esc(player.username)} — *{int(player.points)}pts* \\({player.correct}/{q_played} correct\\)\n"
    return text


def build_mini_leaderboard(session: QuizSession) -> str:
    leaderboard = session.get_leaderboard()
    medals = ["🥇", "🥈", "🥉"]
    text = f"🏆 *STANDINGS*\n{SEP}\n"

    if not leaderboard:
        text += "_No scores yet_\n"
        return text

    for i, player in enumerate(leaderboard[:10]):
        new_rank = i + 1
        arrow = _rank_arrow(player, new_rank)
        medal = medals[i] if i < 3 else f"{new_rank}\\."
        text += f"{medal} @{esc(player.username)} — *{int(player.points)}pts*{arrow}\n"

    if len(leaderboard) > 10:
        text += "┄┄┄┄┄┄\n"
        for i, player in enumerate(leaderboard[10:], start=11):
            arrow = _rank_arrow(player, i)
            text += f"{i}\\. @{esc(player.username)} — {int(player.points)}pts{arrow}\n"

    return text


def _rank_arrow(player, new_rank: int) -> str:
    if player.previous_rank is None:
        return ""
    if new_rank < player.previous_rank:
        return " 🟢"
    elif new_rank > player.previous_rank:
        return " 🔴"
    return ""


def build_question_message(q: dict, index: int, total: int):
    text = (
        f"🛰️ *QUESTION {index} / {total}*\n"
        f"{SEP}\n\n"
        f"{esc(q['question'])}\n\n"
    )
    for label, option_text in q["options"].items():
        text += f"*{label}\\.* {esc(option_text)}\n"
    text += f"\n{SEP}\n⏱️ _You have {config.QUESTION_TIMER} seconds\\!_"

    buttons = [
        [
            InlineKeyboardButton("A", callback_data="answer:A"),
            InlineKeyboardButton("B", callback_data="answer:B"),
        ],
        [
            InlineKeyboardButton("C", callback_data="answer:C"),
            InlineKeyboardButton("D", callback_data="answer:D"),
        ],
    ]
    return text, InlineKeyboardMarkup(buttons)


# ─────────────────────────────────────────────
# QUIZ FLOW
# ─────────────────────────────────────────────

async def run_question_timer(chat_id: int, message_id: int, q: dict, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(config.QUESTION_TIMER)

    session = active_sessions.get(chat_id)
    if not session or not session.active:
        return

    try:
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id, reply_markup=None
        )
    except Exception:
        pass

    correct_label = q["answer"]
    correct_text = esc(q["options"][correct_label])
    explanation = esc(q.get("explanation", ""))
    q_index = session.current_index + 1
    answered_count = len(session.answered_this_round)

    mini_lb = build_mini_leaderboard(session)

    timesup_text = (
        f"⏰ *TIME'S UP — Q{q_index} / {len(session.questions)}*\n"
        f"{SEP}\n\n"
        f"✅ *{correct_label}\\. {correct_text}*\n"
        f"💡 _{explanation}_\n\n"
        f"👥 _{answered_count} player{'s' if answered_count != 1 else ''} answered_\n\n"
        f"{mini_lb}\n"
        f"_{esc(f'Next question in {config.BETWEEN_QUESTION_DELAY} seconds...')}_"
    )

    sent = await context.bot.send_message(chat_id=chat_id, text=timesup_text, parse_mode=ParseMode.MARKDOWN_V2)
    session.bot_message_ids.append(sent.message_id)

    await asyncio.sleep(config.BETWEEN_QUESTION_DELAY)

    session = active_sessions.get(chat_id)
    if not session or not session.active:
        return

    session.advance()

    if session.is_finished():
        await post_results(chat_id, session, context)
    else:
        await post_question(chat_id, context)


async def post_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    session = active_sessions.get(chat_id)
    if not session or not session.active or session.is_finished():
        return

    q = session.current_question()
    index = session.current_index + 1
    session.snapshot_ranks()
    text, keyboard = build_question_message(q, index, len(session.questions))

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard
    )

    session.bot_message_ids.append(msg.message_id)
    session.current_question_message_id = msg.message_id
    session.question_start_time = time.time()

    if session.timer_task and not session.timer_task.done():
        session.timer_task.cancel()
    session.timer_task = asyncio.create_task(
        run_question_timer(chat_id, msg.message_id, q, context)
    )


async def post_results(chat_id: int, session: QuizSession, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = build_leaderboard_text(session)
    winners = session.get_winners()

    save_questions(session.questions, session.topic)

    if not winners:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🏁 *QUIZ OVER\\!*\n{SEP}\n\n"
                f"🌌 _No one participated this round\\._\n"
                f"_Better luck next time\\!_"
            ),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        await _cleanup_session(chat_id, context)
        return

    winner_ids = {w.user_id for w in winners}
    update_all_time_scores(session.scores, winner_ids)

    if len(winners) == 1:
        winner = winners[0]
        winner_text = (
            f"🏆 *WINNER*\n"
            f"@{esc(winner.username)}\n"
            f"_{int(winner.points)} pts · {winner.correct}/{session.questions_played} correct_"
        )
    else:
        cosmic = await asyncio.to_thread(get_cosmic_random, config)
        winner = cosmic_choice(winners, cosmic["seed"])
        winner_text = (
            f"🤝 *IT'S A TIE\\!*\n"
            f"_Multiple players scored equally\\._\n\n"
            f"🌌 _Cosmic tiebreak via cTRNG\\.\\.\\._\n\n"
            f"🏆 *WINNER: @{esc(winner.username)}*"
        )

    total = get_question_count()
    print(f"[DB] Total questions in database: {total}")

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🏁 *QUIZ COMPLETE\\!*\n"
            f"{SEP}\n\n"
            f"{winner_text}\n\n"
            f"{leaderboard}\n"
            f"{SEP}\n"
            f"📡 _Cosmic source: {esc(session.cosmic_source)}_"
        ),
        parse_mode=ParseMode.MARKDOWN_V2
    )

    # Final results message stays — clean up everything else
    await _cleanup_session(chat_id, context)


# ─────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🛸 *SPACECOMPUTER QUIZ BOT*\n"
        f"{SEP}\n\n"
        f"AI\\-powered quiz with verifiable cosmic randomness\n"
        f"from real satellite hardware\\.\n\n"
        f"*Commands:*\n"
        f"🚀 `/startquiz` — Launch a new round\n"
        f"   `/startquiz topic:cTRNG count:10`\n"
        f"🛑 `/endquiz` — Force end current round\n"
        f"📊 `/leaderboard` — Current round standings\n"
        f"🌟 `/alltime` — Hall of Fame \\(sent to DMs\\)\n"
        f"👤 `/mystats` — Your personal stats \\(sent to DMs\\)\n"
        f"🎯 `/topics` — Available quiz topics\n"
        f"🔄 `/updatekb` — Refresh knowledge base\n\n"
        f"_{SEP}_\n"
        f"_Questions are AI\\-generated\\. Winners selected_\n"
        f"_using cosmic randomness from SpaceComputer cTRNG_ 🌌",
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_only(update, context):
        return
    chat_id = update.effective_chat.id
    lines = [f"{topic_emoji(t)} `{esc(t)}`" for t in config.TOPICS]
    sent = await update.message.reply_text(
        f"🎯 *AVAILABLE TOPICS*\n"
        f"{SEP}\n\n"
        f"{chr(10).join(lines)}\n\n"
        f"_Usage: `/startquiz topic:cTRNG`_\n"
        f"_Custom topics are also supported\\._",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    _schedule(_auto_delete(chat_id, [sent.message_id], context))


async def startquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await group_admin_only(update, context):
        return

    if chat_id in active_sessions and active_sessions[chat_id].active:
        sent = await update.message.reply_text(
            "⚠️ _A quiz is already running\\!_ Use /endquiz to stop it first\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        _schedule(_auto_delete(chat_id, [sent.message_id], context))
        return

    topic = "SpaceComputer and orbital computing"
    count = config.QUESTIONS_PER_ROUND

    if context.args:
        for arg in context.args:
            lower = arg.lower()
            if lower.startswith("topic:"):
                topic = arg.split(":", 1)[1].strip()
            elif lower.startswith("count:"):
                try:
                    count = int(arg.split(":", 1)[1])
                    count = max(config.MIN_QUESTIONS_PER_ROUND, min(count, config.MAX_QUESTIONS_PER_ROUND))
                except ValueError:
                    pass

    launch_text = (
        f"🚀 *LAUNCHING QUIZ ROUND\\!*\n"
        f"{SEP}\n\n"
        f"{topic_emoji(topic)} *Topic:* {esc(topic)}\n"
        f"🔢 *Questions:* {count}\n"
        f"⏱️ *Timer:* {config.QUESTION_TIMER} seconds per question\n"
        f"🌌 *Points:* up to {config.BASE_POINTS} per correct answer\n\n"
        f"_{esc('Fetching cosmic seed & generating questions...')}_"
    )

    pre_session_ids = []
    try:
        if config.QUIZ_BANNER_IMAGE_URL:
            try:
                banner = config.QUIZ_BANNER_IMAGE_URL
                if banner.startswith("http"):
                    photo = banner
                else:
                    # Local file path — resolve relative to the project directory
                    photo = open(os.path.join(os.path.dirname(__file__), banner), "rb")
                sent = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=launch_text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                if hasattr(photo, "close"):
                    photo.close()
            except Exception:
                sent = await update.message.reply_text(launch_text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            sent = await update.message.reply_text(launch_text, parse_mode=ParseMode.MARKDOWN_V2)
        pre_session_ids.append(sent.message_id)

        cosmic = await asyncio.to_thread(get_cosmic_random, config)
        seed = cosmic["seed"]
        print(f"[cTRNG] Seed: {seed} | Source: {cosmic['source']}")

        asked = get_asked_questions()
        print(f"[DB] Passing {len(asked)} previously asked questions to AI")
        questions = await asyncio.to_thread(
            generate_questions,
            config.ANTHROPIC_API_KEY,
            topic,
            count,
            asked
        )

        questions = cosmic_shuffle(questions, seed)
        for q in questions:
            options_items = list(q["options"].items())
            shuffled_options = cosmic_shuffle(options_items, seed + hash(q["question"]))
            new_labels = ["A", "B", "C", "D"]
            old_correct_text = q["options"][q["answer"]]
            q["options"] = {new_labels[i]: shuffled_options[i][1] for i in range(4)}
            for label, text in q["options"].items():
                if text == old_correct_text:
                    q["answer"] = label
                    break

        session = QuizSession(
            chat_id=chat_id,
            questions=questions,
            cosmic_seed=seed,
            cosmic_source=cosmic["source"],
            topic=topic
        )
        session.bot_message_ids.extend(pre_session_ids)
        active_sessions[chat_id] = session

        if cosmic["sequence"]:
            verify_text = (
                f"✅ *QUIZ READY FOR LAUNCH\\!*\n"
                f"{SEP}\n\n"
                f"🌌 *Cosmic Randomness Locked In*\n"
                f"🔢 Pulse \\#{cosmic['sequence']}\n"
                f"🌱 Seed: `{seed}`\n"
                f"📡 `{cosmic['raw'][0][:24]}\\.\\.\\. `\n\n"
                f"🔍 _Verify at:_\n"
                f"`https://ipfs\\.io/ipns/k2k4r8lvomw737sajfnpav0dpeernugnryng50uheyk1k39lursmn09f`\n\n"
                f"{SEP}\n"
                f"_🚀 First question launches in 3 seconds\\.\\.\\._"
            )
        else:
            verify_text = (
                f"✅ *Quiz ready\\!*\n\n"
                f"_🚀 First question launches in 3 seconds\\.\\.\\._"
            )

        verify_sent = await context.bot.send_message(chat_id=chat_id, text=verify_text, parse_mode=ParseMode.MARKDOWN_V2)
        session.bot_message_ids.append(verify_sent.message_id)

        await asyncio.sleep(3)
        await post_question(chat_id, context)

    except Exception as e:
        err = await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ *Failed to start quiz*\n\n_{esc(str(e))}_",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        _schedule(_auto_delete(chat_id, [err.message_id], context))
        if chat_id in active_sessions:
            await _cleanup_session(chat_id, context)
        elif pre_session_ids:
            _schedule(_delete_messages(chat_id, pre_session_ids, context))


async def endquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await group_admin_only(update, context):
        return

    if chat_id not in active_sessions or not active_sessions[chat_id].active:
        sent = await update.message.reply_text("_No active quiz to end\\._", parse_mode=ParseMode.MARKDOWN_V2)
        _schedule(_auto_delete(chat_id, [sent.message_id], context))
        return

    session = active_sessions[chat_id]
    session.active = False
    if session.timer_task and not session.timer_task.done():
        session.timer_task.cancel()

    sent = await update.message.reply_text(
        f"🛑 *Quiz ended by admin\\.*\n_{esc('Tallying results...')}_",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    session.bot_message_ids.append(sent.message_id)

    await post_results(chat_id, session, context)


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await group_admin_only(update, context):
        return

    if chat_id not in active_sessions:
        sent = await update.message.reply_text("_No quiz is currently running\\._", parse_mode=ParseMode.MARKDOWN_V2)
        _schedule(_auto_delete(chat_id, [sent.message_id], context))
        return

    session = active_sessions[chat_id]
    board = session.get_leaderboard()
    if not board:
        sent = await update.message.reply_text("_No scores yet — be the first to answer\\!_", parse_mode=ParseMode.MARKDOWN_V2)
        _schedule(_auto_delete(chat_id, [sent.message_id], context))
        return

    medals = ["🥇", "🥈", "🥉"]
    q_played = session.questions_played
    text = f"📊 *CURRENT STANDINGS*\n{SEP}\n"
    for i, player in enumerate(board[:10]):
        medal = medals[i] if i < 3 else f"{i+1}\\."
        text += f"{medal} @{esc(player.username)} — *{int(player.points)}pts* \\({player.correct}/{q_played} correct\\)\n"
    text += f"\n_Q{session.current_index + 1} of {len(session.questions)} in progress_"
    sent = await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
    _schedule(_auto_delete(chat_id, [sent.message_id], context))


async def alltime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = esc(user.username or user.first_name)

    rows = get_all_time_leaderboard(10)
    if not rows:
        text = f"🌟 *HALL OF FAME*\n{SEP}\n\n_No data yet — play some rounds\\!_"
    else:
        medals = ["🥇", "🥈", "🥉"]
        text = f"🌟 *HALL OF FAME*\n{SEP}\n\n"
        for i, (uname, total_pts, correct, attempted, rounds, wins) in enumerate(rows):
            medal = medals[i] if i < 3 else f"{i+1}\\."
            accuracy = f"{round(correct / attempted * 100)}%" if attempted else "0%"
            text += (
                f"{medal} @{esc(uname)}\n"
                f"   ⭐ *{total_pts:,}pts* · 🏆 {wins}W · 🎮 {rounds} rounds · ✅ {esc(accuracy)}\n"
            )

    await _send_dm_or_warn(update, context, user.id, username, text)


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = esc(user.username or user.first_name)
    chat_id = update.effective_chat.id

    stats = get_player_stats(user_id)
    session = active_sessions.get(chat_id)

    text = f"👤 *@{username}*\n{SEP}\n\n"

    if stats:
        accuracy = (
            f"{round(stats['correct_answers'] / stats['total_attempted'] * 100)}%"
            if stats["total_attempted"] else "0%"
        )
        text += (
            f"*ALL\\-TIME STATS*\n"
            f"🌟 Rank: *\\#{stats['rank']}*\n"
            f"⭐ Points: *{stats['total_points']:,}*\n"
            f"✅ Accuracy: *{esc(accuracy)}* \\({stats['correct_answers']}/{stats['total_attempted']}\\)\n"
            f"🏆 Wins: *{stats['wins']}*\n"
            f"🎮 Rounds played: *{stats['rounds_played']}*\n"
        )
    else:
        text += "_No all\\-time stats yet — join a quiz round\\!_\n"

    if session:
        player = session.scores.get(user_id)
        if player:
            rank = session.get_player_rank(user_id)
            q_played = session.questions_played
            text += (
                f"\n*THIS ROUND*\n"
                f"🏅 Rank: *\\#{rank}*\n"
                f"⭐ Points: *{int(player.points)}*\n"
                f"✅ Correct: *{player.correct}/{q_played}*\n"
            )
        else:
            text += f"\n_You haven't answered any questions this round yet\\._\n"

    await _send_dm_or_warn(update, context, user_id, username, text)


async def updatekb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_admin_only(update, context):
        return

    from knowledge_base import SOURCES
    msg = await update.message.reply_text(
        f"🔄 *Updating knowledge base\\.\\.\\.*\n{SEP}\n\n"
        f"_Fetching {len(SOURCES)} sources\\._\n"
        f"_This takes about 30 seconds\\.\\.\\._",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    chat_id = update.effective_chat.id
    try:
        result = await asyncio.to_thread(build_knowledge_base)
        size_str = esc(f"{result['size_kb']:.1f}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=(
                f"✅ *Knowledge base updated\\!*\n{SEP}\n\n"
                f"📡 Sources fetched: *{result['sources_fetched']}/{result['sources_total']}*\n"
                f"💾 Size: *{size_str} KB*\n\n"
                f"_AI will use the new content on the next quiz round\\._"
            ),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=f"❌ *Update failed*\n\n_{esc(str(e))}_",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    _schedule(_auto_delete(chat_id, [msg.message_id], context))


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    session = active_sessions.get(chat_id)

    if not session or not session.active or session.is_finished():
        try:
            await query.answer("No active quiz right now.", show_alert=True)
        except Exception:
            pass
        return

    data = query.data
    if not data.startswith("answer:"):
        try:
            await query.answer()
        except Exception:
            pass
        return

    answer = data.split(":")[1].upper()
    user = query.from_user
    user_id = user.id
    username = user.username or user.first_name

    print(f"[BUTTON] @{username} tapped {answer}")

    if user_id in session.answered_this_round:
        try:
            await query.answer("You already answered this question!", show_alert=True)
        except Exception:
            pass
        return

    time_taken = time.time() - session.question_start_time
    session.record_answer(user_id, username, answer, time_taken, config.BASE_POINTS, config.QUESTION_TIMER)

    try:
        await query.answer("⏳ Answer recorded!", show_alert=True)
    except Exception as e:
        print(f"[ERROR] query.answer failed: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

async def main():
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("startquiz", startquiz_command))
    app.add_handler(CommandHandler("endquiz", endquiz_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("alltime", alltime_command))
    app.add_handler(CommandHandler("mystats", mystats_command))
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(CommandHandler("updatekb", updatekb_command))
    app.add_handler(CallbackQueryHandler(handle_button, pattern="^answer:"))

    init_db()
    print("🛰️ SpaceComputer Quiz Bot is running...")

    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
