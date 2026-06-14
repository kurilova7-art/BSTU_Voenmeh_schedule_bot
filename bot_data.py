from typing import Dict, Optional
from utils.schedule_parser import ScheduleParser
from utils.storage import load_user_data

schedule_parser: Optional[ScheduleParser] = None
user_states: Dict[int, dict] = load_user_data()


