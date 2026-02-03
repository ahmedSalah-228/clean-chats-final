# Clean Chats

Clean Chats analysis system for conversation quality evaluation.

## Files

- **clean_chats_core.py**: Core analysis logic and conversation flagging handlers
- **clean_chats_config.py**: Configuration for departments, metrics, and flagging criteria
- **clean_chats_storage.py**: Snowflake database storage operations
- **clean_chats_integration.py**: Integration utilities and helpers

## Features

- Multi-department support (CC_Resolvers, MV_Resolvers, CC_Sales, MV_Sales, Gulf_maids, AT_African, AT_Ethiopian, AT_Filipina, Doctors, MV_Delighters)
- Comprehensive metric tracking:
  - Wrong Tool Detection
  - Missing Tool Detection
  - Wrong Answer Detection
  - Policy Violations (Missing/Unclear)
  - Repetition Detection
  - Unresponsive Behavior
  - Interventions Tracking
  - And more...

## Recent Updates

- Added robust LLM key variation support for CC_Resolvers tool detection
- Added empty dict `{}` handling for clean conversations
- Added single tool object format support
- Implemented Wrong Answer detection for Sales departments
- Implemented Gulf_maids tool detection with custom JSON structure
