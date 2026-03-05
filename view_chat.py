# view_chat.py

import argparse
import json
import sqlite3
from pathlib import Path

# Define the path to the database file relative to the project root.
DB_PATH = Path(__file__).parent / "app" / "db" / "chat_history.sqlite3"


def fetch_and_print_chat(user_id: int):
    """
    Connects to the SQLite database, fetches the chat history for a specific
    user ID, and prints it to the console in a readable format.

    Args:
        user_id: The ID of the user (session_id) whose chat history to retrieve.
    """
    if not DB_PATH.is_file():
        print(f"Error: Database file not found at '{DB_PATH}'")
        return

    try:
        # Connect to the SQLite database in read-only mode for safety.
        # The URI=True parameter is necessary for mode specification.
        with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
            cursor = conn.cursor()

            # Fetch all messages for the given session_id, ordered by their insertion.
            cursor.execute(
                "SELECT message FROM chat_history WHERE session_id = ? ORDER BY id ASC",
                (str(user_id),),  # session_id is stored as TEXT
            )
            rows = cursor.fetchall()

            if not rows:
                print(f"No chat history found for user_id: {user_id}")
                return

            print("-" * 50)
            print(f"Chat History for user_id: {user_id}")
            print("-" * 50)

            # Process and print each message.
            for row in rows:
                try:
                    # The message is stored as a JSON string in the first column.
                    message_data = json.loads(row[0])
                    # LangChain message objects have a nested structure.
                    # The type is at the top level, but content is inside the 'data' key.
                    msg_type = message_data.get("type", "unknown").upper()
                    content = message_data.get("data", {}).get("content", "")

                    # Format the output based on the message type.
                    if msg_type == "HUMAN":
                        print(f"[USER]: {content}\n")
                    elif msg_type == "AI":
                        print(f"[BOT]:  {content}\n")
                    else:
                        print(f"[{msg_type}]: {content}\n")

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[ERROR] Could not parse message: {row[0]}. Reason: {e}")

            print("-" * 50)

    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    # Set up the command-line argument parser.
    parser = argparse.ArgumentParser(
        description="View chat history for a specific user from the SQLite database."
    )
    parser.add_argument(
        "user_id", type=int, help="The user_id (session_id) to retrieve chat history for."
    )
    args = parser.parse_args()

    # Run the main function with the provided user_id.
    fetch_and_print_chat(args.user_id)