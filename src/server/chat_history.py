import json
import os
import time
from pathlib import Path
from typing import List, Optional

from openai import AzureOpenAI

from .config import ServerSettings
from .models import ChatMessage, ChatSession, ChatSessionSummary


class ChatHistoryManager:
    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self.history_dir = Path("chat_history")
        self.history_dir.mkdir(exist_ok=True)

    def _get_project_dir(self, project: str) -> Path:
        project_dir = self.history_dir / project
        project_dir.mkdir(exist_ok=True)
        return project_dir

    def save_session(self, project: str, messages: List[ChatMessage], session_id: Optional[str] = None) -> ChatSession:
        project_dir = self._get_project_dir(project)

        existing_session = None
        if session_id:
            existing_session = self.get_session(project, session_id)

        if existing_session:
            # Update existing session
            created_at = existing_session.created_at
            description = existing_session.description
            final_session_id = existing_session.id

            # Update description every 6 messages (approx 3 turns) or if it's the default
            # We check if we added enough new messages to warrant a re-summary
            if len(messages) > len(existing_session.messages) and (
                len(messages) % 6 == 0 or description == "Chat Session"
            ):
                description = self._generate_description(messages)
        else:
            # Create new session
            final_session_id = f"{int(time.time())}-{os.urandom(4).hex()}"
            created_at = time.time()
            description = self._generate_description(messages)

        session = ChatSession(
            id=final_session_id,
            project=project,
            created_at=created_at,
            description=description,
            messages=messages
        )

        file_path = project_dir / f"{final_session_id}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(session.json())

        return session

    def list_sessions(self, project: str) -> List[ChatSessionSummary]:
        project_dir = self._get_project_dir(project)
        sessions = []

        for file_path in project_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Count only user and assistant messages with content
                    msg_count = sum(
                        1 for m in data.get("messages", [])
                        if m.get("role") in ["user", "assistant"] and m.get("content")
                    )

                    sessions.append(ChatSessionSummary(
                        id=data["id"],
                        project=data["project"],
                        created_at=data["created_at"],
                        description=data["description"],
                        message_count=msg_count
                    ))
            except Exception as e:
                print(f"Error loading chat session {file_path}: {e}")

        # Sort by created_at desc
        sessions.sort(key=lambda x: x.created_at, reverse=True)
        return sessions

    def get_session(self, project: str, session_id: str) -> Optional[ChatSession]:
        project_dir = self._get_project_dir(project)
        file_path = project_dir / f"{session_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ChatSession(**data)
        except Exception as e:
            print(f"Error loading chat session {file_path}: {e}")
            return None

    def delete_session(self, project: str, session_id: str) -> bool:
        project_dir = self._get_project_dir(project)
        file_path = project_dir / f"{session_id}.json"

        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def _generate_description(self, messages: List[ChatMessage]) -> str:
        if not messages:
            return "Empty chat"

        # Filter out system messages and tool outputs for the summary
        conversation_text = ""
        for msg in messages[:10]:  # Use first 10 messages for context
            if msg.role in ["user", "assistant"]:
                conversation_text += f"{msg.role}: {msg.content}\n"

        if not conversation_text:
            return "No conversation content"

        try:
            # Use default endpoint if not set in environment (matching agent.py)
            default_endpoint = "https://slagousis-eastus-resource.cognitiveservices.azure.com/"

            api_key = os.environ.get("AZURE_OPENAI_API_KEY")
            if not api_key:
                print("DEBUG: AZURE_OPENAI_API_KEY not found in environment.")
                return "Chat Session"

            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5")
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", default_endpoint)

            print(
                f"DEBUG: Generating summary with deployment='{deployment}', "
                f"version='{api_version}', endpoint='{endpoint}'"
            )
            # print(f"DEBUG: Conversation text: {conversation_text[:200]}...")

            client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint,
            )

            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate a short, descriptive title (3-6 words) for this conversation. "
                            "Focus on the user's intent (e.g., 'Sales Analysis', 'Customer Query', 'Schema Update'). "
                            "Do not use quotes."
                        )
                    },
                    {"role": "user", "content": conversation_text}
                ],
                max_completion_tokens=50
            )

            print(f"DEBUG: Full response choices[0]: {response.choices[0]}")
            print(f"DEBUG: Finish reason: {response.choices[0].finish_reason}")

            content = response.choices[0].message.content
            print(f"DEBUG: Generated summary content: '{content}'")

            if content:
                return content.strip().strip('"')
            return "Chat Session"
        except Exception as e:
            print(f"Error generating summary: {e}")
            return "Chat Session"
