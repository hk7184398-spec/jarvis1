"""
JARVIS Meeting Assistant
Handles meeting scheduling, joining, transcription, and management
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class Meeting:
    """Represents a meeting or call."""
    id: str
    title: str
    platform: str  # zoom, teams, google_meet, etc.
    start_time: datetime
    duration_minutes: int
    participants: List[str] = None
    meeting_url: Optional[str] = None
    notes: str = ""
    transcription: Optional[str] = None
    
    def __post_init__(self):
        if self.participants is None:
            self.participants = []


class MeetingAssistant:
    """Manages meetings and calls."""
    
    def __init__(self):
        self.meetings: Dict[str, Meeting] = {}
        self.current_meeting: Optional[Meeting] = None
    
    def create_meeting(
        self,
        title: str,
        platform: str,
        start_time: datetime,
        duration_minutes: int,
        participants: Optional[List[str]] = None,
        meeting_url: Optional[str] = None
    ) -> Meeting:
        """Create a new meeting."""
        meeting_id = f"mtg_{datetime.now().timestamp()}"
        meeting = Meeting(
            id=meeting_id,
            title=title,
            platform=platform,
            start_time=start_time,
            duration_minutes=duration_minutes,
            participants=participants or [],
            meeting_url=meeting_url
        )
        self.meetings[meeting_id] = meeting
        return meeting
    
    def join_meeting(self, meeting_id: str) -> bool:
        """Join a meeting."""
        meeting = self.meetings.get(meeting_id)
        if meeting:
            self.current_meeting = meeting
            return True
        return False
    
    def leave_meeting(self) -> bool:
        """Leave the current meeting."""
        if self.current_meeting:
            self.current_meeting = None
            return True
        return False
    
    def add_note(self, note: str) -> bool:
        """Add a note to the current meeting."""
        if self.current_meeting:
            self.current_meeting.notes += f"\n{note}"
            return True
        return False
    
    def get_upcoming_meetings(self, hours_ahead: int = 24) -> List[Meeting]:
        """Get upcoming meetings in the next N hours."""
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)
        
        return [
            m for m in self.meetings.values()
            if now <= m.start_time <= cutoff
        ]
    
    def get_meeting(self, meeting_id: str) -> Optional[Meeting]:
        """Get a meeting by ID."""
        return self.meetings.get(meeting_id)
    
    def send_meeting_reminder(self, meeting_id: str) -> str:
        """Send a reminder for a meeting."""
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return "Meeting not found"
        
        reminder = f"Reminder: {meeting.title} starts at {meeting.start_time.strftime('%H:%M')}"
        if meeting.meeting_url:
            reminder += f"\nJoin: {meeting.meeting_url}"
        
        return reminder
    
    def transcribe_meeting(self, meeting_id: str, audio_path: str) -> bool:
        """
        Transcribe a meeting recording.
        Note: Requires speech-to-text service integration.
        """
        meeting = self.meetings.get(meeting_id)
        if not meeting:
            return False
        
        try:
            # Placeholder for transcription service
            # meeting.transcription = transcribe_audio(audio_path)
            return True
        except Exception:
            return False


# Global meeting assistant instance
_meeting_assistant = None


def get_meeting_assistant() -> MeetingAssistant:
    """Get or create the global meeting assistant."""
    global _meeting_assistant
    if _meeting_assistant is None:
        _meeting_assistant = MeetingAssistant()
    return _meeting_assistant
