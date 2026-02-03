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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                {
                    'table': 'MISSING_POLICY_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_yes',
                    'description': 'Missing policy detected (missingPolicy = Yes)'
                },
                {
                    'table': 'WRONG_TOOL_RAW_DATA',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'cc_resolvers_properly_called_no',
                    'description': 'Wrong tool detected (properlyCalled = No in array)'
                },
                {
                    'table': 'MISSING_TOOL_RAW_DATA',
                    'prompt_type': 'missed_tool_call',
                    'flagging_criteria': 'cc_resolvers_missed_call_yes',
                    'description': 'Missed tool call detected (missedCall = Yes in tool objects)'
                },
                 {
                    'table': 'CC_RESOLVERS_UNCLEAR_POLICY_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'confusing_policy_yes',
                    'description': 'Unclear policy detected (confusingPolicy = Yes)'
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'WRONG_TOOL_SUMMARY',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'not_properly_called_count',
                    'description': 'Wrong tool usage detected (not_properly_called_count > 0)'
                },
                # {
                #     'table': 'MISSING_TOOL_SUMMARY',
                #     'prompt_type': 'missed_tool_call',
                #     'flagging_criteria': 'missed_called_count',
                #     'description': 'Missed tool call detected (missed_called_count > 0)'
                # },
                # {
                #     'table': 'TOOL_EVAL_SUMMARY',
                #     'prompt_type': 'wrong_tool',
                #     'flagging_criteria': 'wrong_tool_pct',
                #     'description': 'Wrong tool usage detected (WRONG_PCT > 0)'
                # },
                # {
                #     'table': 'TOOL_EVAL_SUMMARY',
                #     'prompt_type': 'missed_tool_call',
                #     'flagging_criteria': 'missing_tool_pct',
                #     'description': 'Missed tool calls detected (MISSING_PCT > 0)'
                # },
                {
                    'table': 'UNCLEAR_POLICY_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'confusing_policy_yes',
                    'description': 'Unclear policy detected (confusingPolicy = Yes)'
                },
                {
                    'table': 'MISSING_POLICY_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_yes',
                    'description': 'Missing policy detected (missingPolicy = Yes)'
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                {
                    'table': 'MISSING_POLICY_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'doctors_missing_policy_detected',
                    'description': 'Missing policy detected (missing_policy_detected = true)'
                },
                {
                    'table': 'WRONG_TOOL_RAW_DATA',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'cc_resolvers_properly_called_no',
                    'description': 'Wrong tool detected (properlyCalled = No in array)'
                },
                {
                    'table': 'MISSING_TOOL_RAW_DATA',
                    'prompt_type': 'missed_tool_call',
                    'flagging_criteria': 'cc_resolvers_missed_call_yes',
                    'description': 'Missed tool call detected (missedCall = Yes in tool objects)'
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'wrong_answer',
                    'flagging_criteria': 'wrong_answer_violation',
                    'description': 'Wrong Answer violation detected in policy violations array'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'unclear_policy_violation',
                    'description': 'Unclear Policy violation detected in policy violations array'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_violation',
                    'description': 'Missing Policy violation detected in policy violations array'
                }
            
            ]
        },
        'AT_Filipina_In_PHL': {
            'department': 'AT_Filipina_In_PHL',
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'wrong_answer',
                    'flagging_criteria': 'wrong_answer_violation',
                    'description': 'Wrong Answer violation detected in policy violations array'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'unclear_policy_violation',
                    'description': 'Unclear Policy violation detected in policy violations array'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_violation',
                    'description': 'Missing Policy violation detected in policy violations array'
                }
            
            ]
        },
        'AT_Filipina_Outside_UAE': {
            'department': 'AT_Filipina_Outside_UAE',
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'wrong_answer',
                    'flagging_criteria': 'wrong_answer_violation',
                    'description': 'Wrong Answer violation detected in policy violations array'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'unclear_policy_violation',
                    'description': 'Unclear Policy violation detected in policy violations array'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_violation',
                    'description': 'Missing Policy violation detected in policy violations array'
                }
            
            ]
        },
        'AT_Filipina_Inside_UAE': {
            'department': 'AT_Filipina_Inside_UAE',
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'wrong_answer',
                    'flagging_criteria': 'wrong_answer_violation',
                    'description': 'Wrong Answer violation detected in policy violations array'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'unclear_policy_violation',
                    'description': 'Unclear Policy violation detected in policy violations array'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_violation',
                    'description': 'Missing Policy violation detected in policy violations array'
                }
            
            ]
        },
        
        # Add other departments with their specific configurations
        'MV_Delighters': {
            'department': 'MV_Delighters',
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'WRONG_TOOL_SUMMARY',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'not_properly_called_count',
                    'description': 'Wrong tool usage detected (not_properly_called_count > 0)'
                },
                {
                    'table': 'MISSING_TOOL_SUMMARY',
                    'prompt_type': 'missed_tool_call',
                    'flagging_criteria': 'missed_called_count',
                    'description': 'Missed tool call detected (missed_called_count > 0)'
                },
                {
                    'table': 'UNCLEAR_POLICY_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'confusing_policy_yes',
                    'description': 'Unclear policy detected (confusingPolicy = Yes)'
                },
                {
                    'table': 'MISSING_POLICY_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_yes',
                    'description': 'Missing policy detected (missingPolicy = Yes)'
                }

            ]
        },
        'CC_Delighters': {
            'department': 'CC_Delighters',
            'flagging_tables': [
                
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },

                {
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                {
                    'table': 'WRONG_TOOL_SUMMARY',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'not_properly_called_count',
                    'description': 'Wrong tool usage detected (not_properly_called_count > 0)'
                },
                {
                    'table': 'cc_delighters_missed_tool_summary',
                    'prompt_type': 'missed_tool_call',
                    'flagging_criteria': 'missed_called_count',
                    'description': 'Missed tool call detected (missed_called_count > 0)'
                },
                {
                    'table': 'UNCLEAR_POLICY_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'confusing_policy_yes',
                    'description': 'Unclear policy detected (confusingPolicy = Yes)'
                },
                {
                    'table': 'MISSING_POLICY_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_yes',
                    'description': 'Missing policy detected (missingPolicy = Yes)'
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                # {
                #     'table': 'TOOL_RAW_DATA',
                #     'prompt_type': 'wrong_tool',
                #     'flagging_criteria': 'wrong_tool_issue_type',
                #     'description': 'Wrong tool called detected in ANALYSIS_REPORT'
                # },
                # {
                #     'table': 'TOOL_RAW_DATA',
                #     'prompt_type': 'missed_tool_call',
                #     'flagging_criteria': 'missed_tool_issue_type',
                #     'description': 'Missed tool call detected in ANALYSIS_REPORT'
                # },
                {
                    'table': 'TOOL_EVAL_SUMMARY',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'wrong_tool_pct',
                    'description': 'Wrong tool usage detected (WRONG_PCT > 0)'
                },
                {
                    'table': 'TOOL_EVAL_SUMMARY',
                    'prompt_type': 'missed_tool_call',
                    'flagging_criteria': 'missing_tool_pct',
                    'description': 'Missed tool calls detected (MISSING_PCT > 0)'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'unclear_policy_issue_type',
                    'description': 'Unclear policy detected in ANALYSIS_REPORT'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_issue_type',
                    'description': 'Missing policy detected in ANALYSIS_REPORT'
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
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'TOOL_RAW_DATA',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'wrong_tool_issue_type',
                    'description': 'Wrong tool called detected in ANALYSIS_REPORT'
                },
                {
                    'table': 'TOOL_RAW_DATA',
                    'prompt_type': 'missed_tool_call',
                    'flagging_criteria': 'missed_tool_issue_type',
                    'description': 'Missed tool call detected in ANALYSIS_REPORT'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'unclear_policy',
                    'flagging_criteria': 'unclear_policy_issue_type',
                    'description': 'Unclear policy detected in ANALYSIS_REPORT'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'missing_policy',
                    'flagging_criteria': 'missing_policy_issue_type',
                    'description': 'Missing policy detected in ANALYSIS_REPORT'
                }
            ]
        },
        
        'CC_Sales': {
            'department': 'CC_Sales',
            'flagging_tables': [
                # {
                #     'table': 'clarity_score_raw_data',
                #     'prompt_type': 'clarity_score',
                #     'flagging_criteria': 'clarification_count',
                #     'description': 'Clarity issues detected (clarification messages > 0)'
                # },
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                
    
                {
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'TOOL_SUMMARY',
                    'prompt_type': 'wrong_tool_cc_sales_only',
                    'flagging_criteria': 'wrong_tool_percentage',
                    'description': 'Wrong tool usage detected in CC_Sales (WRONG_TOOL_PERCENTAGE > 0)'
                },
                {
                    'table': 'TOOL_SUMMARY',
                    'prompt_type': 'missed_tool_cc_sales_only',
                    'flagging_criteria': 'missing_tool_percentage',
                    'description': 'Missed tool calls detected in CC_Sales (MISSING_TOOL_PERCENTAGE > 0)'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'cc_sales_unclear_policy',
                    'flagging_criteria': 'cc_sales_unclear_policy_true',
                    'description': 'CC_Sales unclear policy detected (unclear_policy = true)'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'cc_sales_missing_policy',
                    'flagging_criteria': 'cc_sales_missing_policy_true',
                    'description': 'CC_Sales missing policy detected (missing_policy = true)'
                },
                {
                    'table': 'WRONG_ANSWER_RAW_DATA',
                    'prompt_type': 'wrong_answer',
                    'flagging_criteria': 'sales_wrong_answer_true',
                    'description': 'Wrong answer detected (wrong_answer = true)'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                }

            ]
        },
        
        'MV_Sales': {
            'department': 'MV_Sales',
            'flagging_tables': [
                
                # {
                #     'table': 'clarity_score_raw_data',
                #     'prompt_type': 'clarity_score',
                #     'flagging_criteria': 'clarification_count',
                #     'description': 'Clarity issues detected (clarification messages > 0)'
                # },
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                
   
                {
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                # {
                #     'table': 'TOOL_SUMMARY',
                #     'prompt_type': 'wrong_tool_cc_sales_only',
                #     'flagging_criteria': 'wrong_tool_percentage',
                #     'description': 'Wrong tool usage detected in CC_Sales (WRONG_TOOL_PERCENTAGE > 0)'
                # },
                # {
                #     'table': 'TOOL_SUMMARY',
                #     'prompt_type': 'missed_tool_cc_sales_only',
                #     'flagging_criteria': 'missing_tool_percentage',
                #     'description': 'Missed tool calls detected in CC_Sales (MISSING_TOOL_PERCENTAGE > 0)'
                # },
                {
                    'table': 'TOOL_EVAL_SUMMARY',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'wrong_tool_pct',
                    'description': 'Wrong tool usage detected (WRONG_PCT > 0)'
                },
                {
                    'table': 'TOOL_EVAL_SUMMARY',
                    'prompt_type': 'missed_tool_call',
                    'flagging_criteria': 'missing_tool_pct',
                    'description': 'Missed tool calls detected (MISSING_PCT > 0)'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'cc_sales_unclear_policy',
                    'flagging_criteria': 'cc_sales_unclear_policy_true',
                    'description': 'CC_Sales unclear policy detected (unclear_policy = true)'
                },
                {
                    'table': 'POLICY_VIOLATION_RAW_DATA',
                    'prompt_type': 'cc_sales_missing_policy',
                    'flagging_criteria': 'cc_sales_missing_policy_true',
                    'description': 'CC_Sales missing policy detected (missing_policy = true)'
                },
                {
                    'table': 'WRONG_ANSWER_RAW_DATA',
                    'prompt_type': 'wrong_answer',
                    'flagging_criteria': 'sales_wrong_answer_true',
                    'description': 'Wrong answer detected (wrong_answer = true)'
                }
            ]
        },
        'Gulf_maids': {
            'department': 'Gulf_maids',
            'flagging_tables': [
                
              
                {
                    'table': 'REPETITION_RAW_DATA',
                    'prompt_type': 'repetition',
                    'flagging_criteria': 'exists_only',
                    'description': 'Repetition issues detected'
                },
                
   
                {
                    'table': 'INTERVENTIONS_CONVERSATIONS',
                    'prompt_type': 'interventions',
                    'flagging_criteria': 'exists_only',
                    'description': 'at least 1 intervention detected'
                },
                {
                    'table': 'UNRESPONSIVE_RAW_DATA',
                    'prompt_type': 'unresponsive',
                    'flagging_criteria': 'exists_only',
                    'description': 'Unresponsive behavior detected'
                },
                {
                    'table': 'TOOL_RAW_DATA',
                    'prompt_type': 'wrong_tool',
                    'flagging_criteria': 'gulf_maids_wrong_tool',
                    'description': 'Wrong tool detected (Wrong Calls > 0 in Tool Calls Summary)'
                },
                {
                    'table': 'TOOL_RAW_DATA',
                    'prompt_type': 'missed_tool_call',
                    'flagging_criteria': 'gulf_maids_missing_tool',
                    'description': 'Missing tool detected (Tool Name != None in Missing Tools)'
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
        
        # Individual flagging source counts
        'FALSE_PROMISES_COUNT': 'INTEGER',
        'LEGAL_ALIGNMENT_COUNT': 'INTEGER',
        'REPETITION_COUNT': 'INTEGER',
        'UNRESPONSIVE_COUNT': 'INTEGER',
        'REPORTED_ISSUES_COUNT': 'INTEGER',
        'INTERVENTIONS_COUNT': 'INTEGER',
        'MISPRESCRIPTION_COUNT': 'INTEGER',
        'UNNECESSARY_CLINIC_COUNT': 'INTEGER',
        'CLARITY_SCORE_COUNT': 'INTEGER',
        'WRONG_TOOL_COUNT': 'INTEGER',
        'MISSED_TOOL_CALL_COUNT': 'INTEGER',
        'UNCLEAR_POLICY_COUNT': 'INTEGER',
        'MISSING_POLICY_COUNT': 'INTEGER',
        'WRONG_ANSWER_COUNT': 'INTEGER',
        
        'ANALYSIS_TIMESTAMP': 'TIMESTAMP'
    }

def get_clean_chats_raw_data_schema():
    """
    Define schema for clean chats raw data table with individual flagging columns
    """
    return {
        'DATE': 'DATE',
        'DEPARTMENT': 'VARCHAR(100)',
        'CONVERSATION_ID': 'VARCHAR(500)',
        'CUSTOMER_NAME': 'VARCHAR(500)',
        'AGENT_NAMES': 'VARCHAR(1000)',
        'LAST_SKILL': 'VARCHAR(500)',
        'IS_CLEAN': 'VARCHAR(20)',  # TRUE/FALSE/NOT_ASSESSED
        
        # Individual flagging system columns (YES/NO/N_A/NOT_ASSESSED)
        'FALSE_PROMISES': 'VARCHAR(15)',
        'LEGAL_ALIGNMENT': 'VARCHAR(15)',
        'REPETITION': 'VARCHAR(15)',
        'UNRESPONSIVE': 'VARCHAR(15)',
        'REPORTED_ISSUES': 'VARCHAR(15)',
        'INTERVENTIONS': 'VARCHAR(15)',
        'MISPRESCRIPTION': 'VARCHAR(15)',
        'UNNECESSARY_CLINIC': 'VARCHAR(15)',
        'CLARITY_SCORE': 'VARCHAR(15)',
        'WRONG_TOOL': 'VARCHAR(15)',
        'MISSED_TOOL_CALL': 'VARCHAR(15)',
        'UNCLEAR_POLICY': 'VARCHAR(15)',
        'MISSING_POLICY': 'VARCHAR(15)',
        'WRONG_ANSWER': 'VARCHAR(15)',
        
        'ANALYSIS_TIMESTAMP': 'TIMESTAMP'
    }

def get_clean_chats_detail_schema():
    """
    Legacy function - use get_clean_chats_raw_data_schema() instead
    """
    return get_clean_chats_raw_data_schema()

def get_department_flagging_applicability():
    """
    Define which flagging systems apply to which departments
    Returns mapping of department -> flagging_system -> True/False
    """
    return {
        'CC_Resolvers': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'MISSING_POLICY': True
        },
        'MV_Resolvers': {
            'FALSE_PROMISES': True,
            'LEGAL_ALIGNMENT': True,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True
        },
        'Doctors': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': True,
            'UNNECESSARY_CLINIC': True,
            'CLARITY_SCORE': True,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'MISSING_POLICY': True
        },
        'AT_Filipina': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': False,
            'MISSED_TOOL_CALL': False,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True,
            'WRONG_ANSWER': True
        },
        'AT_Filipina_In_PHL': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': False,
            'MISSED_TOOL_CALL': False,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True,
            'WRONG_ANSWER': True
        },
        'AT_Filipina_Outside_UAE': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': False,
            'MISSED_TOOL_CALL': False,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True,
            'WRONG_ANSWER': True
        },
        'AT_Filipina_Inside_UAE': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': False,
            'MISSED_TOOL_CALL': False,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True,
            'WRONG_ANSWER': True
        },
        'AT_Ethiopian': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True
        },
        'AT_African': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True
        },
        'MV_Delighters': {
            'FALSE_PROMISES': True,
            'LEGAL_ALIGNMENT': True,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True
        },
        'CC_Delighters': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True
        },
        'CC_Sales': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True,
            'WRONG_ANSWER': True
        },
        'MV_Sales': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'UNCLEAR_POLICY': True,
            'MISSING_POLICY': True,
            'WRONG_ANSWER': True
        },
        'Gulf_maids': {
            'FALSE_PROMISES': False,
            'LEGAL_ALIGNMENT': False,
            'REPETITION': True,
            'UNRESPONSIVE': True,
            'REPORTED_ISSUES': False,
            'INTERVENTIONS': True,
            'MISPRESCRIPTION': False,
            'UNNECESSARY_CLINIC': False,
            'CLARITY_SCORE': False,
            'WRONG_TOOL': True,
            'MISSED_TOOL_CALL': True,
            'UNCLEAR_POLICY': False,
            'MISSING_POLICY': False,
            'WRONG_ANSWER': False
        }
    }

def get_flagging_system_mapping():
    """
    Map flagging table configurations to standardized flagging system names
    """
    return {
        # Map prompt_type to standardized column names
        'false_promises': 'FALSE_PROMISES',
        'legal_alignment': 'LEGAL_ALIGNMENT', 
        'repetition': 'REPETITION',
        'unresponsive': 'UNRESPONSIVE',
        'reported_issues': 'REPORTED_ISSUES',
        'interventions': 'INTERVENTIONS',
        'misprescription': 'MISPRESCRIPTION',
        'unnecessary_clinic': 'UNNECESSARY_CLINIC',
        'clarity_score': 'CLARITY_SCORE',
        'wrong_tool': 'WRONG_TOOL',
        'missed_tool_call': 'MISSED_TOOL_CALL',
        'wrong_tool_cc_sales_only': 'WRONG_TOOL',
        'missed_tool_cc_sales_only': 'MISSED_TOOL_CALL',
        
        # Policy-related mappings (MV_Resolvers)
        'unclear_policy': 'UNCLEAR_POLICY',
        'missing_policy': 'MISSING_POLICY',
        
        # Policy-related mappings (CC_Sales - different naming)
        'cc_sales_unclear_policy': 'UNCLEAR_POLICY',
        'cc_sales_missing_policy': 'MISSING_POLICY',
        
        # Wrong Answer mapping (AT_Filipina)
        'wrong_answer': 'WRONG_ANSWER'
    }

def get_llm_response_based_criteria():
    """
    Define which flagging criteria use LLM_RESPONSE and need error checking
    """
    return {
        'nps_score_1': 'SA_NPS',  # JSON parsing for NPS score
        'contains_yes': 'GENERIC_YES',  # LLM response contains "YES"
        'contains_true': 'GENERIC_TRUE',  # LLM response contains "TRUE"  
        'contains_rogue_answer': 'FALSE_PROMISES',  # LLM response contains "RogueAnswer"
        'clarification_count': 'CLARITY_SCORE',  # JSON parsing for clarification count
        'avoid_visit': 'UNNECESSARY_CLINIC',  # JSON parsing for could_avoid_visit
        'not_properly_called_count': 'WRONG_TOOL',  # Check if not_properly_called_count > 0
        'missed_called_count': 'MISSED_TOOL_CALL',  # Check if missed_called_count > 0
        'wrong_tool_percentage': 'WRONG_TOOL',  # Check if WRONG_TOOL_PERCENTAGE > 0 (CC_Sales)
        'missing_tool_percentage': 'MISSED_TOOL_CALL',  # Check if MISSING_TOOL_PERCENTAGE > 0 (CC_Sales)
        'wrong_tool_pct': 'WRONG_TOOL',  # Check if WRONG_PCT > 0 (Generic - TOOL_EVAL_SUMMARY)
        'missing_tool_pct': 'MISSED_TOOL_CALL',  # Check if MISSING_PCT > 0 (Generic - TOOL_EVAL_SUMMARY)
        'confusing_policy_yes': 'UNCLEAR_POLICY',  # Check if confusingPolicy = "Yes" in JSON response
        'missing_policy_yes': 'MISSING_POLICY',  # Check if missingPolicy = "Yes" in JSON response
        'cc_sales_unclear_policy_true': 'UNCLEAR_POLICY',  # Check if unclear_policy = true in JSON response (CC_Sales)
        'cc_sales_missing_policy_true': 'MISSING_POLICY',  # Check if missing_policy = true in JSON response (CC_Sales)
        'wrong_answer_violation': 'WRONG_ANSWER',  # Check if violations array contains violation_type = "Wrong Answer" (AT_Filipina)
        'unclear_policy_violation': 'UNCLEAR_POLICY',  # Check if violations array contains violation_type = "Unclear Policy" (AT_Filipina)
        'missing_policy_violation': 'MISSING_POLICY',  # Check if violations array contains violation_type = "missing policy" (AT_Filipina)
        'wrong_tool_issue_type': 'WRONG_TOOL',  # Check ANALYSIS_REPORT for ISSUE_TYPE = "WRONG_TOOL_CALLED" (AT_African, AT_Ethiopian)
        'missed_tool_issue_type': 'MISSED_TOOL_CALL',  # Check ANALYSIS_REPORT for ISSUE_TYPE = "MISSED_TO_BE_CALLED" (AT_African, AT_Ethiopian)
        'unclear_policy_issue_type': 'UNCLEAR_POLICY',  # Check ANALYSIS_REPORT for ISSUE_TYPE = "UNCLEAR_POLICY_AMBIGUITY" (AT_African, AT_Ethiopian)
        'missing_policy_issue_type': 'MISSING_POLICY',  # Check ANALYSIS_REPORT for ISSUE_TYPE = "MISSING_POLICY_ADHERENCE" (AT_African, AT_Ethiopian)
        'doctors_missing_policy_detected': 'MISSING_POLICY',  # Check if missing_policy_detected = true in JSON response (Doctors)
        'cc_resolvers_properly_called_no': 'WRONG_TOOL',  # Check if properlyCalled = "No" in array of tools (CC_Resolvers)
        'cc_resolvers_missed_call_yes': 'MISSED_TOOL_CALL',  # Check if missedCall = "Yes" in tool objects dict (CC_Resolvers)
        'sales_wrong_answer_true': 'WRONG_ANSWER',  # Check if wrong_answer = true in JSON response (CC_Sales, MV_Sales)
        'gulf_maids_wrong_tool': 'WRONG_TOOL',  # Check if Wrong Calls > 0 in Tool Calls Summary (Gulf_maids)
        'gulf_maids_missing_tool': 'MISSED_TOOL_CALL'  # Check if Tool Name != None in Missing Tools (Gulf_maids)
    }

def get_table_existence_based_criteria():
    """
    Define which flagging criteria only check table existence (no LLM_RESPONSE)
    """
    return [
        'exists_only'  # Just checks if conversation exists in table
    ]

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
        },
        'not_properly_called_count': {
            'description': 'Check if not_properly_called_count > 0 for any record with same conversation ID',
            'applicable_to': ['WRONG_TOOL_SUMMARY'],
            'example': 'Flags conversations where tools were not properly called'
        },
        'missed_called_count': {
            'description': 'Check if missed_called_count > 0 for any record with same conversation ID',
            'applicable_to': ['MISSING_TOOL_SUMMARY'],
            'example': 'Flags conversations where tool calls were missed'
        },
        'wrong_tool_percentage': {
            'description': 'Check if WRONG_TOOL_PERCENTAGE > 0 for any record with same conversation ID (CC_Sales only)',
            'applicable_to': ['TOOL_SUMMARY'],
            'example': 'Flags CC_Sales conversations where wrong tool percentage is greater than 0'
        },
        'missing_tool_percentage': {
            'description': 'Check if MISSING_TOOL_PERCENTAGE > 0 for any record with same conversation ID (CC_Sales only)',
            'applicable_to': ['TOOL_SUMMARY'],
            'example': 'Flags CC_Sales conversations where missing tool percentage is greater than 0'
        },
        'wrong_tool_pct': {
            'description': 'Check if WRONG_PCT > 0 for any record with same conversation ID (Generic tool evaluation)',
            'applicable_to': ['TOOL_EVAL_SUMMARY'],
            'example': 'Flags conversations where wrong tool percentage is greater than 0'
        },
        'missing_tool_pct': {
            'description': 'Check if MISSING_PCT > 0 for any record with same conversation ID (Generic tool evaluation)',
            'applicable_to': ['TOOL_EVAL_SUMMARY'],
            'example': 'Flags conversations where missing tool percentage is greater than 0'
        },
        'is_parsed_false': {
            'description': 'Check if IS_PARSED = FALSE for any record with same conversation ID (MV_Resolvers missed_tool_call only)',
            'applicable_to': ['MISSING_TOOL_RAW_DATA'],
            'example': 'Flags conversations where LLM parsing failed for missed tool analysis, marking them as NOT_ASSESSED'
        },
        'is_parsed_false_wrong_tool': {
            'description': 'Check if IS_PARSED = FALSE for any record with same conversation ID (MV_Resolvers wrong_tool only)',
            'applicable_to': ['WRONG_TOOL_RAW_DATA'],
            'example': 'Flags conversations where LLM parsing failed for wrong tool analysis, marking them as NOT_ASSESSED'
        },
        'is_parsed_false_cc_sales_wrong_tool': {
            'description': 'Check if IS_PARSED = FALSE for any record with same conversation ID (CC_Sales wrong_tool_cc_sales_only)',
            'applicable_to': ['TOOL_RAW_DATA'],
            'example': 'Flags conversations where LLM parsing failed for CC_Sales wrong tool analysis, marking them as NOT_ASSESSED'
        },
        'is_parsed_false_cc_sales_missing_tool': {
            'description': 'Check if IS_PARSED = FALSE for any record with same conversation ID (CC_Sales missed_tool_cc_sales_only)',
            'applicable_to': ['TOOL_RAW_DATA'], 
            'example': 'Flags conversations where LLM parsing failed for CC_Sales missing tool analysis, marking them as NOT_ASSESSED'
        },
        'confusing_policy_yes': {
            'description': 'Parse JSON response and check if confusingPolicy = "Yes" (case insensitive)',
            'applicable_to': ['UNCLEAR_POLICY_RAW_DATA'],
            'example': 'Flags conversations where LLM detected confusing policy issues'
        },
        'missing_policy_yes': {
            'description': 'Parse JSON response and check if missingPolicy = "Yes" (case insensitive)',
            'applicable_to': ['MISSING_POLICY_RAW_DATA'],
            'example': 'Flags conversations where LLM detected missing policy issues'
        },
        'cc_sales_unclear_policy_true': {
            'description': 'Parse JSON response and check if unclear_policy = true (case insensitive) - CC_Sales only',
            'applicable_to': ['POLICY_VIOLATION_RAW_DATA'],
            'example': 'Flags CC_Sales conversations where LLM detected unclear policy violations'
        },
        'cc_sales_missing_policy_true': {
            'description': 'Parse JSON response and check if missing_policy = true (case insensitive) - CC_Sales only',
            'applicable_to': ['POLICY_VIOLATION_RAW_DATA'],
            'example': 'Flags CC_Sales conversations where LLM detected missing policy violations'
        },
        'is_parsed_false_cc_sales_policy': {
            'description': 'Check if IS_PARSED = FALSE for any record with same conversation ID (CC_Sales policy violations)',
            'applicable_to': ['POLICY_VIOLATION_RAW_DATA'],
            'example': 'Flags conversations where LLM parsing failed for CC_Sales policy analysis, marking them as NOT_ASSESSED'
        }
    }
