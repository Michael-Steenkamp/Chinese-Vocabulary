import json
import os
import random
import sys
import time
from typing import Any, Dict, List, Tuple

# ==========================================
# -------- Penalties and Rewards -----------
# ==========================================
# New values to create a more balanced system.
# It now takes ~4 correct answers (base reward) to
# counteract 1 incorrect penalty.
# This rewards consistency.
PENALTY_HINT = 1.5
PENALTY_SKIP = 3.0
PENALTY_INCORRECT = 4.0
REWARD_STREAK = 0.25  # Bonus per item in streak
REWARD_TIME = 0.5   # Bonus for beating avg time
REWARD_CORRECT = 1.0  # Base reward for correct
MAX_WEIGHT = 10.0
MIN_WEIGHT = 0.01

# ==========================================
# ------------ File Paths ------------------
# ==========================================
HSK_PATH = "json/"
PROGRESS_PATH = "progress/"
DEFAULT_HSK = 1

# ==========================================
# ------------ Global Flags ----------------
# ==========================================
# These will be set by user input
g_chinese_to_english = True
g_random_mode = True
g_show_pinyin = True
g_show_simplified = True
g_show_meta_data = True

# ==========================================
# ------------ Global Variables ------------
# ==========================================
# These will be set by get_hsk_file()
g_progress_file_path = ""
g_hsk_level = 0
g_in_order_index = 0  # Used only if g_random_mode is False


# ==========================================
# ----------------- Icons ------------------
# ==========================================
# (From your existing code)
icon_proficiency = "🧠"  # nf-fa-poll (for the weight/proficiency %)
icon_time = "  "         # nf-fa-clock_o (for total time)
icon_streak = "  "       # nf-fa-bolt (lightning bolt)
icon_accuracy = "  "    # nf-fa-bullseye (a good one for accuracy)
# (New icons)
icon_seen = "  "         # nf-fa-eye (for "words seen")
icon_mastery = "⭐"      # nf-fa-star (for "words mastered")
icon_warning = "⚠"      # nf-fa-warning (for hints, etc.)
icon_correct = "✔ "      # nf-fa-check
icon_incorrect = "✖ "    # nf-fa-times
# ==========================================
# ----------- Helper Functions -------------
# ==========================================

def clear_terminal():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def tokenize_input(user_input: str) -> List[str]:
    """Splits user input into uppercase tokens."""
    return [token.upper() for token in user_input.replace("-", " ").split() if token.strip()]


# ==========================================
# -------- Session Setup Functions ---------
# ==========================================

def get_hsk_file() -> List[Dict[str, Any]]:
    """
    Prompts the user to select an HSK level (1-4) and loads the
    corresponding JSON file. Sets global paths.
    """
    global g_hsk_level, g_progress_file_path
    while True:
        print("Select HSK Level (1-4)")
        inpt = input("> ")

        try:
            if not inpt:
                g_hsk_level = DEFAULT_HSK
            else:
                g_hsk_level = int(inpt)

            g_progress_file_path = f"{PROGRESS_PATH}hsk{str(g_hsk_level)}-progress.json"
            if 1 <= g_hsk_level <= 4:
                hsk_file = f"{HSK_PATH}hsk{str(g_hsk_level)}.json"
                try:
                    with open(hsk_file, 'r', encoding="utf-8") as f:
                        return json.load(f)
                except FileNotFoundError:
                    print(f"File not found: {hsk_file}")
                    print("Ensure file hierarchy: {JSON/HSK1-4.json}")
                except json.JSONDecodeError:
                    print(f"Invalid JSON format in: {hsk_file}")
                except Exception as e:
                    print(f"Unexpected error: {e}")
            else:
                print(f"Invalid Option ({inpt}) - must be between 1-4")

        except ValueError:
            print("Please enter a valid number (1-4)")


def display_session_settings():
    """Prints the current session settings."""
    print("Chinese -> English" if g_chinese_to_english else "English -> Chinese", " | ",
          "Random" if g_random_mode else "In-Order", " | ",
          "Display Pinyin" if g_show_pinyin else "No Pinyin", " | ",
          "Display Simplified" if g_show_simplified else "No Simplified", " | ",
          "Display Meta Data" if g_show_meta_data else "No Meta Data")


def set_session_settings():
    """
    Displays session settings and prompts the user for
    customizations via command flags.
    """
    print("#----- Session Specifications -----#")
    display_session_settings()
    print("#-- Customization --#")
    print("English -> Chinese [-ec]")
    print("Toggle Random      [-r]")
    print("Toggle Pinyin      [-p]")
    print("Toggle Simplified  [-s]")
    print("Toggle Meta Data   [-m]")
    print("Quit               [-q]")

    inpt = input("> ").strip()
    tokens = tokenize_input(inpt)
    while not validate_tokens(tokens):
        inpt = input("> ").strip()
        tokens = tokenize_input(inpt)

    print("#----- Session -----#")
    display_session_settings()


def validate_tokens(tokens: List[str]) -> bool:
    """
    Parses user input tokens and toggles global settings.
    Returns False if any tokens are invalid.
    """
    global g_chinese_to_english, g_random_mode, g_show_pinyin
    global g_show_simplified, g_show_meta_data
    errs = []
    for token in tokens:
        if token == "Q":
            sys.exit(0)
        elif token == "EC":
            g_chinese_to_english = not g_chinese_to_english
        elif token == "R":
            g_random_mode = not g_random_mode
        elif token == "P":
            g_show_pinyin = not g_show_pinyin
        elif token == "S":
            g_show_simplified = not g_show_simplified
        elif token == "M":
            g_show_meta_data = not g_show_meta_data
        else:
            errs.append(token)

    if errs:
        print("Error: Invalid Arguments ->", errs)
        return False
    return True


def show_quiz_options():
    """Prints the available options during a quiz."""
    print("#-- Options --#")
    print("~ Skip   [-s]")
    print("~ Hint   [-h]")
    print("~ Quit   [-q]")


# ==========================================
# -------- Progress Functions --------------
# ==========================================

def get_default_progress(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Creates a new progress list with default max weight."""
    return [{
        "word": w.get('simplified', 'N/A'),
        "weight": MAX_WEIGHT,
        "streak": 0,
        "avg_time": 0.0,
        "total_time": 0.0,
        "attempts": 0,
        "correct": 0
    } for w in data]


def load_progress(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Loads progress from the global progress file.
    Intelligently merges old progress with new data so adding words
    doesn't reset your stats.
    """
    if not os.path.exists(g_progress_file_path):
        return get_default_progress(data)
    try:
        with open(g_progress_file_path, 'r', encoding="utf-8") as f:
            old_prog = json.load(f)

        # Create a lookup dictionary from the old progress
        # Key = word (simplified character), Value = the progress dictionary
        old_prog_map = {item['word']: item for item in old_prog if 'word' in item}

        new_prog = []
        for w in data:
            word_char = w.get('simplified', 'N/A')

            # If we have history for this word, use it
            if word_char in old_prog_map:
                new_prog.append(old_prog_map[word_char])
            else:
                # Otherwise, create a new default entry for the new word
                new_prog.append({
                    "word": word_char,
                    "weight": MAX_WEIGHT,
                    "streak": 0,
                    "avg_time": 0.0,
                    "total_time": 0.0,
                    "attempts": 0,
                    "correct": 0
                })

        return new_prog

    except (json.JSONDecodeError, IOError):
        print(f"Error reading progress file, starting fresh.")
        return get_default_progress(data)


def save_progress(progress_data: List[Dict[str, Any]]):
    """Saves the progress list to the global progress file."""
    try:
        # Ensure the progress directory exists
        os.makedirs(PROGRESS_PATH, exist_ok=True)
        with open(g_progress_file_path, 'w', encoding="utf-8") as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Error saving progress: {e}")


# ==========================================
# ----------- Quiz Logic -------------------
# ==========================================

def get_next_index(data_len: int, progress: List[Dict[str, Any]]) -> int:
    """
    Gets the index for the next quiz item.
    Either randomly (based on weights) or sequentially.
    """
    global g_in_order_index
    if g_random_mode:
        weights = [item["weight"] for item in progress]
        indices = list(range(data_len))
        # random.choices returns a list, so we take the first element [0]
        selected_index = random.choices(indices, weights=weights, k=1)[0]
    else:
        selected_index = g_in_order_index
        g_in_order_index = (g_in_order_index + 1) % data_len
    return selected_index


def get_quiz_item_data(item: Dict[str, Any]) -> Tuple[List[str], List[str], str]:
    """Extracts the prompt, answer, and hint from a data item."""
    hint = [item.get('example_cn', 'No example')]
    answer = []
    prompt = "〘 "

    if g_chinese_to_english:
        prompt += item.get('english_concise', 'N/A') + " | " + item.get("english_descriptive", 'N/A') + " 〙"
        if g_show_simplified:
            prompt += "\n〘 " + item.get('simplified', 'N/A') + " 〙"

        answer.append(item.get("simplified", "").lower())
        # Handle pinyin answer (e.g., "ni3hao3")
        if 'pinyin' in item and isinstance(item['pinyin'], list) and len(item['pinyin']) > 1:
            answer.append(item['pinyin'][1].replace(" ", "").lower())
        else:
             answer.append(item.get('pinyin', '').replace(" ", "").lower())

    else: # English to Chinese
        prompt = "〘 " + item.get('simplified', 'N/A')
        if g_show_pinyin:
            prompt += f" ({item.get('pinyin', 'N/A')})"
        prompt += " 〙"
        answer.append(item.get("english_concise", "N/A").lower())
        hint.append(str(item.get('categories', 'No category')))

    return answer, hint, prompt


def reveal_answer(item: Dict[str, Any]):
    """Prints the full details for a word (used after wrong answer)."""
    measure_word = item.get('measure_word', {})
    mw_char = measure_word.get('character', '')
    mw_pinyin = measure_word.get('pinyin', '')

    print("╔")
    print(f"║ ⌜ {item.get('simplified', 'N/A')} | {item.get('pinyin', 'N/A')} ({mw_char} {mw_pinyin})")
    print(f"║ ⌞ {item.get('english_concise', 'N/A')} | {item.get('english_descriptive', 'N/A')}")
    print("║")
    print(f"║ ⌜ {item.get('example_cn', 'N/A')} ({item.get('example_pinyin', 'N/A')})")
    print(f"║ ⌞ {item.get('example_en', 'N/A')}")
    print("╚")


def check_answer(user_input: str, answer_list: List[str]) -> bool:
    """Checks if the user's input matches any valid answer."""
    if g_chinese_to_english:
        # Accept Chinese characters or pinyin
        return user_input in answer_list
    else:
        # Accept any part of the concise English answer
        return user_input in answer_list[0]
    return False


def display_item_metadata(prog_item: Dict[str, Any], orig_weight: float):
    """Shows the stats for the item that was just quizzed."""
    if not g_show_meta_data:
        return

    # Calculate "proficiency" for this single item (0-100%)
    # 100% = MIN_WEIGHT (mastered)
    # 0%   = MAX_WEIGHT (unseen)
    weight_range = MAX_WEIGHT - MIN_WEIGHT
    new_proficiency = ((MAX_WEIGHT - prog_item['weight']) / weight_range) * 100.0
    old_proficiency = ((MAX_WEIGHT - orig_weight) / weight_range) * 100.0
    proficiency_change = new_proficiency - old_proficiency

    accuracy = (prog_item['correct'] / prog_item['attempts']) * 100.0 if prog_item['attempts'] > 0 else 0.0

    print("╔")
    print(f"║ {icon_accuracy}{accuracy:.2f}% ({prog_item['correct']} / {prog_item['attempts']})")
    print(f"║ {icon_proficiency} {new_proficiency:.2f}% ({'+' if proficiency_change > 0.0 else ''}{proficiency_change:.2f}%)")
    print(f"║ {icon_streak}{prog_item['streak']}")
    print(f"║ {icon_time}{prog_item['avg_time']:.2f}s avg")
    print("╚")


def run_quiz_for_item(item: Dict[str, Any], prog_item: Dict[str, Any]) -> str:
    """
    Runs the full quiz logic for a single item.
    Handles input, checking, and weight updates.
    Returns a status string: "correct", "incorrect", "skipped", "quit".
    """
    print("-" * 30)
    input("Press Enter To Continue...")
    clear_terminal()
    print()

    answer, hint, prompt = get_quiz_item_data(item)
    print(prompt)

    start_time = time.time()
    inpt = input(" ").strip().lower()
    end_time = time.time()

    elapsed_time = end_time - start_time
    orig_weight = prog_item['weight']

    # --- Handle special commands ---
    if inpt == "-q":
        print("Quitting session...")
        return "quit"
    if inpt == "-s":
        print(f"Skipped. The answer was: {answer[0]}")
        prog_item['weight'] = min(MAX_WEIGHT, prog_item['weight'] + PENALTY_SKIP)
        prog_item['streak'] = 0
        prog_item['attempts'] += 1 # Skipping counts as an attempt
        display_item_metadata(prog_item, orig_weight)
        return "skipped"
    if inpt == "-h":
        print(f"Hint: {hint[0]}")
        prog_item['weight'] = min(MAX_WEIGHT, prog_item['weight'] + PENALTY_HINT)
        # Re-prompt for answer after hint
        start_time_after_hint = time.time()
        inpt = input(f" [ {icon_warning} ] ").strip().lower()
        end_time_after_hint = time.time()
        elapsed_time += (end_time_after_hint - start_time_after_hint)

    # --- Update time stats (always) ---
    prog_item['attempts'] += 1
    prog_item['total_time'] += elapsed_time

    # --- Check the answer ---
    if check_answer(inpt, answer):
        print(f"{icon_correct}Correct (⏱ {elapsed_time:.2f}s)〘 {item.get('example_cn', '')}〙")
        prog_item['correct'] += 1
        prog_item['streak'] += 1

        # Apply rewards
        reward = (REWARD_CORRECT + (REWARD_STREAK * prog_item['streak']))
        if prog_item['avg_time'] > 0 and elapsed_time < prog_item['avg_time']:
            reward += REWARD_TIME

        prog_item['weight'] = max(MIN_WEIGHT, prog_item['weight'] - reward)
        result = "correct"
    else:
        reveal_answer(item)
        print(f"{icon_incorrect}Incorrect (⏱ {elapsed_time:.2f}s)")
        prog_item['streak'] = 0
        prog_item['weight'] = min(MAX_WEIGHT, prog_item['weight'] + PENALTY_INCORRECT)
        result = "incorrect"

    # Update avg_time *after* processing
    prog_item['avg_time'] = prog_item['total_time'] / prog_item['attempts']

    # Display the metadata for this specific item
    display_item_metadata(prog_item, orig_weight)

    return result


# ==========================================
# --------- Statistics Functions -----------
# ==========================================

def get_session_metadata(progress: List[Dict[str, Any]]) -> Tuple[float, float]:
    """
    Calculates the total (overall) proficiency and total time spent.
    """
    if not progress:
        return 0.0, 0.0

    total_weight = sum(p['weight'] for p in progress)
    total_time = sum(p['total_time'] for p in progress)

    avg_weight = total_weight / len(progress)
    weight_range = MAX_WEIGHT - MIN_WEIGHT

    # Normalized difficulty: 0.0 = easy (MIN_WEIGHT), 1.0 = hard (MAX_WEIGHT)
    normalized_avg_difficulty = (avg_weight - MIN_WEIGHT) / weight_range

    # Proficiency: 100.0 = easy, 0.0 = hard
    proficiency_percent = (1.0 - normalized_avg_difficulty) * 100.0

    # Clamp values just in case
    proficiency_percent = max(0.0, min(100.0, proficiency_percent))

    return proficiency_percent, total_time

def display_session_summary(
    progress: List[Dict[str, Any]],
    session_correct: int,
    session_attempts: int,
    time_change_minutes: float,
    start_proficiency: float):
    """
    Displays a final summary of the session and overall HSK progress.
    """

    # --- Calculate Session-Specific Stats ---
    session_accuracy = (session_correct / session_attempts * 100) if session_attempts > 0 else 0

    # --- Calculate Updated Global Stats ---
    end_proficiency, end_total_time = get_session_metadata(progress)
    proficiency_change = end_proficiency - start_proficiency

    total_words = len(progress)
    words_seen = sum(1 for p in progress if p['attempts'] > 0)

    # --- New: Calculate Overall Accuracy ---
    overall_total_correct = sum(p['correct'] for p in progress)
    overall_total_attempts = sum(p['attempts'] for p in progress)
    overall_accuracy = (overall_total_correct / overall_total_attempts * 100) if overall_total_attempts > 0 else 0

    # Define "mastered" as 95%+ proficiency (or weight in the bottom 5% of the range)
    mastery_threshold = MIN_WEIGHT + (MAX_WEIGHT - MIN_WEIGHT) * 0.05
    words_mastered = sum(1 for p in progress if p['weight'] <= mastery_threshold)

    # --- Display the Stats Boxes ---
    clear_terminal()
    print()
    print(f"╔══ Session Summary (HSK {g_hsk_level}) ══════════════")
    print(f"║ {icon_time}Time:        +{time_change_minutes:.2f} minutes")
    print(f"║ {icon_accuracy}Accuracy:     {session_accuracy:.1f}% ({session_correct} / {session_attempts})")
    print(f"║ {icon_proficiency} Change:      {'+' if proficiency_change > 0 else ''}{proficiency_change:.2f}%")
    print("╚" + "═" * 41)

    print()

    print(f"╔══ Overall Progress (HSK {g_hsk_level}) ══════════════")
    print(f"║ {icon_proficiency} Proficiency:  {end_proficiency:.1f}%")
    # --- This is the new line ---
    print(f"║ {icon_accuracy}Accuracy:     {overall_accuracy:.1f}% ({overall_total_correct}/{overall_total_attempts})")
    print(f"║ {icon_seen}Seen:         {words_seen} / {total_words} words")
    print(f"║ {icon_mastery} Mastered:     {words_mastered} / {total_words} words")
    print(f"║ {icon_time}Total Time:   {end_total_time / 3600:.2f} hours")
    print("╚" + "═" * 41)
    print()
    input("Press Enter To Exit...")

# ==========================================
# ----------------- MAIN -------------------
# ==========================================
def main():
    """
    Main function to run the HSK quiz.
    """
    try:
        data = get_hsk_file()
        progress = load_progress(data)
        set_session_settings()
        show_quiz_options()

        session_correct = 0
        session_attempts = 0

        # Get initial proficiency
        start_proficiency, start_total_time = get_session_metadata(progress)

        while True:
            index = get_next_index(len(data), progress)

            item_data = data[index]
            item_progress = progress[index]

            result = run_quiz_for_item(item_data, item_progress)

            if result == "correct":
                session_correct += 1
                session_attempts += 1
            elif result == "incorrect" or result == "skipped":
                session_attempts += 1
            elif result == "quit":
                break  # User quit

    except KeyboardInterrupt:
        print("\nSession interrupted. Saving progress...")
    finally:
        # Always save progress on exit
        if 'progress' in locals():
            # 1. Save the updated progress first
            save_progress(progress)

            # 2. Get the NEW total time from the progress data
            end_proficiency, end_total_time = get_session_metadata(progress)

            # 3. Calculate the change *between the two totals*
            time_change_minutes = (end_total_time - start_total_time) / 60.0

            clear_terminal()
            display_session_summary(
                progress=progress,
                session_correct=session_correct,
                session_attempts=session_attempts,
                time_change_minutes=time_change_minutes,
                start_proficiency=start_proficiency
            )
        else:
            print("Exiting.")

if __name__ == "__main__":
    main()
