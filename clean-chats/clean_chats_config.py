"""
Clean Chats Configuration Module
Imports and adapts configurations from LLM_JUDGE for clean chat analysis
"""

import sys
import os

# Add LLM_JUDGE to path for imports
llm_judge_path = "/Users/ahmedsalah/Projects/Clean Chats/LLM_JUDGE"
if llm_judge_path not in sys.path:
    sys.path.append(llm_judge_path)

# Import configurations from LLM_JUDGE
from snowflake_llm_config import (
    get_snowflake_llm_departments_config,
    get_metrics_configuration,
    list_all_output_tables,
    get_snowflake_base_departments_config
)

def get_clean_chats_departments_config():
    """
    Get department configurations for clean chats analysis
    Uses the same configs as LLM_JUDGE
    """
    return get_snowflake_llm_departments_config()

def get_clean_chats_flagging_config():
    """
    Define which raw tables and criteria indicate "flagged" conversations per department
    
    Returns:
        Dictionary mapping departments to their flagging tables and criteria
    """
    
    # MANUAL CONFIGURATION: Define exactly which tables to check per department
    flagging_config = {
        'CC_Resolvers': {
            'department': 'CC_Resolvers',
            'flagging_tables': [
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }
                
            ]
        },
        
        'MV_Resolvers': {
            'department': 'MV_Resolvers', 
            'flagging_tables': [
                
                {
                    'table': 'FALSE_PROMISES_RAW_DATA',
                    'prompt_type': 'false_promises',
                    'flagging_criteria': 'contains_rogue_answer',
                    'description': 'False promises detection'
                },
               
                {
                    'table': 'LEGAL_ALIGNMENT_RAW_DATA',
                    'prompt_type': 'legal_alignment',
                    'flagging_criteria': 'contains_true',
                    'description': 'Legal alignment issues'
                },
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }
          
                
                # Add only the tables you want to check for MV_Resolvers
                # Comment out or remove tables you don't want to include
            ]
        },
        
        'Doctors': {
            'department': 'Doctors',
            'flagging_tables': [
                {
                    'table': 'DOCTORS_MISPRESCRIPTION_RAW_DATA',
                    'prompt_type': 'misprescription',
                    'flagging_criteria': 'contains_true',
                    'description': 'Medical misprescription detection'
                },
                {
                    'table': 'DOCTORS_UNNECESSARY_CLINIC_RAW_DATA',
                    'prompt_type': 'unnecessary_clinic',
                    'flagging_criteria': 'avoid_visit',
                    'description': 'Unnecessary clinic recommendation - could avoid visit'
                },
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                
                {
                    'table': 'clarity_score_raw_data',
                    'prompt_type': 'clarity_score',
                    'flagging_criteria': 'clarification_count',
                    'description': 'Clarity issues detected (clarification messages > 0)'
                },
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }
            ]
        },
        
        'AT_Filipina': {
            'department': 'AT_Filipina',
            'flagging_tables': [
                
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }
            
            ]
        },
        
        # Add other departments with their specific configurations
        'Delighters': {
            'department': 'Delighters',
            'flagging_tables': [
                
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }

            ]
        },
        
        'AT_African': {
            'department': 'AT_African',
            'flagging_tables': [
                
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }
            ]
        },
        
        'AT_Ethiopian': {
            'department': 'AT_Ethiopian',
            'flagging_tables': [
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }
            ]
        },
        
        'CC_Sales': {
            'department': 'CC_Sales',
            'flagging_tables': [
                {
                    'table': 'clarity_score_raw_data',
                    'prompt_type': 'clarity_score',
                    'flagging_criteria': 'clarification_count',
                    'description': 'Clarity issues detected (clarification messages > 0)'
                },
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }
            ]
        },
        
        'MV_Sales': {
            'department': 'MV_Sales',
            'flagging_tables': [
                
                {
                    'table': 'clarity_score_raw_data',
                    'prompt_type': 'clarity_score',
                    'flagging_criteria': 'clarification_count',
                    'description': 'Clarity issues detected (clarification messages > 0)'
                },
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                
                {
                    'table': 'CHATCC_REPORTED_ISSUES',
                    'prompt_type': 'reported_issues',
                    'flagging_criteria': 'exists_only',
                    'description': 'Reported issues detected'
                }
            ]
        }
    }
    
    # Add total_flagging_sources count for each department
    for dept_name, config in flagging_config.items():
        config['total_flagging_sources'] = len(config['flagging_tables'])
    
    return flagging_config

def get_department_flagging_tables(department_name):
    """
    Get list of flagging tables for a specific department
    
    Args:
        department_name: Department name
        
    Returns:
        List of flagging table configurations
    """
    flagging_config = get_clean_chats_flagging_config()
    return flagging_config.get(department_name, {}).get('flagging_tables', [])

def list_all_clean_chats_departments():
    """
    Get list of all departments available for clean chats analysis
    """
    return list(get_clean_chats_departments_config().keys())

def get_clean_chats_summary_schema():
    """
    Define schema for clean chats summary table
    """
    return {
        'DATE': 'DATE',
        'DEPARTMENT': 'VARCHAR(100)',
        'TOTAL_CONVERSATIONS': 'INTEGER',
        'CLEAN_CONVERSATIONS': 'INTEGER',
        'FLAGGED_CONVERSATIONS': 'INTEGER',
        'CLEAN_PERCENTAGE': 'FLOAT',
        'FLAGGED_BY_SA_NPS': 'INTEGER',
        'FLAGGED_BY_SPECIALIZED_PROMPTS': 'INTEGER',
        'FLAGGING_BREAKDOWN': 'VARCHAR(5000)',  # JSON string of flagging details
        'ANALYSIS_TIMESTAMP': 'TIMESTAMP'
    }

def get_clean_chats_detail_schema():
    """
    Define schema for detailed clean chats table (conversation-level)
    """
    return {
        'DATE': 'DATE',
        'DEPARTMENT': 'VARCHAR(100)',
        'CONVERSATION_ID': 'VARCHAR(500)',
        'CUSTOMER_NAME': 'VARCHAR(500)',
        'AGENT_NAMES': 'VARCHAR(1000)',
        'LAST_SKILL': 'VARCHAR(500)',
        'IS_CLEAN': 'BOOLEAN',
        'FLAGGING_SOURCES': 'VARCHAR(2000)',  # Comma-separated list of flagging sources
        'FLAGGING_DETAILS': 'VARCHAR(5000)',  # JSON string with detailed flagging info
        'ANALYSIS_TIMESTAMP': 'TIMESTAMP'
    }

def add_custom_flagging_criteria(department_name, table_name, prompt_type, criteria, description):
    """
    Helper function to add custom flagging criteria to a department
    
    Args:
        department_name: Department to modify
        table_name: Raw table to check
        prompt_type: Prompt type identifier
        criteria: Flagging criteria ('nps_score_1', 'contains_yes', 'custom_sql')
        description: Human-readable description
    
    Example:
        add_custom_flagging_criteria(
            'MV_Resolvers', 
            'CLARITY_SCORE_RAW_DATA', 
            'clarity_score', 
            'contains_yes', 
            'Low clarity score detection'
        )
    """
    config = get_clean_chats_flagging_config()
    
    if department_name in config:
        new_table = {
            'table': table_name,
            'prompt_type': prompt_type,
            'flagging_criteria': criteria,
            'description': description
        }
        config[department_name]['flagging_tables'].append(new_table)
        config[department_name]['total_flagging_sources'] += 1
        
        print(f"✅ Added {table_name} to {department_name} flagging config")
    else:
        print(f"❌ Department {department_name} not found")
    
    return config

def get_available_flagging_criteria():
    """
    Get list of supported flagging criteria types
    """
    return {
        'nps_score_1': {
            'description': 'Check if SA_prompt NPS score equals 1',
            'applicable_to': ['SA_RAW_DATA'],
            'example': 'Flags conversations with poor sentiment (NPS = 1)'
        },
        'contains_yes': {
            'description': 'Check if LLM response contains "YES"',
            'applicable_to': ['All specialized prompt tables'],
            'example': 'Flags when LLM detects an issue (responds with YES)'
        },
        'contains_true': {
            'description': 'Check if LLM response contains "TRUE"',
            'applicable_to': ['All specialized prompt tables'],
            'example': 'Flags when LLM detects an issue (responds with TRUE)'
        },
        'contains_rogue_answer': {
            'description': 'Check if LLM response contains "RogueAnswer"',
            'applicable_to': ['All specialized prompt tables'],
            'example': 'Flags when LLM detects rogue or unexpected responses'
        },
        'exists_only': {
            'description': 'Check if conversation ID exists in table (regardless of response)',
            'applicable_to': ['All specialized prompt tables'],
            'example': 'Flags conversations where the mere presence indicates an issue'
        },
        'clarification_count': {
            'description': 'Parse JSON response and check if ClarificationMessages > 0',
            'applicable_to': ['clarity_score_raw_data'],
            'example': 'Flags conversations requiring clarification (communication unclear)'
        },
        'avoid_visit': {
            'description': 'Parse JSON response and check if could_avoid_visit is true',
            'applicable_to': ['DOCTORS_UNNECESSARY_CLINIC_RAW_DATA'],
            'example': 'Flags conversations where clinic visit could have been avoided'
        },
        'nps_score_range': {
            'description': 'Check NPS score within a range (1-2, 1-3, etc.)',
            'applicable_to': ['SA_RAW_DATA'],
            'example': 'Flags conversations with NPS scores 1-2 (poor to neutral)'
        },
        'contains_text': {
            'description': 'Check if LLM response contains specific text',
            'applicable_to': ['All tables'],
            'example': 'Flags when response contains custom keywords'
        }
    }
