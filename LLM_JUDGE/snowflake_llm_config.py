"""
LLM Configuration Module for Snowflake Chat Analysis
Defines department configurations, prompts, and model preferences
"""

from prompts import *
from snowflake_llm_metrics_calc import *

def get_snowflake_base_departments_config():
    """
    Base department configuration from existing snowflake_phase2_core_analytics.py
    Maps department names to their bot_skills, agent_skills, and Snowflake table names.
    """
    return {
        'CC_Resolvers': {
            'bot_skills': ['GPT_CC_RESOLVERS'],
            'agent_skills': ['CC_RESOLVERS_AGENTS', 'DDC_AGENTS', 'GPT CC Shadowers'],
            'table_name': 'LLM_EVAL.RAW_DATA.CC_CLIENT_CHATS',
            'skill_filter': 'gpt_cc_resolvers',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'ChatGPT CC Resolvers'
        },
        'MV_Resolvers': {
            'bot_skills': ['GPT_MV_RESOLVERS'],
            'agent_skills': ['MV_RESOLVERS_SENIORS', 'MV_CALLERS', 'MV_RESOLVERS_MANAGER', 
                           'GPT_MV_RESOLVERS_SHADOWERS', 'GPT_MV_RESOLVERS_SHADOWERS_MANAGER'],
            'table_name': 'LLM_EVAL.RAW_DATA.MV_CLIENT_CHATS',
            'skill_filter': 'gpt_mv_resolvers',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'MV Resolvers V2'
        },
        'CC_Sales': {
            'bot_skills': ['GPT_CC_PROSPECT'],
            'agent_skills': ['GPT CC Shadowers', 'CHATGPT_SALES_SHADOWERS'],
            'table_name': 'LLM_EVAL.RAW_DATA.CC_SALES_CHATS',
            'skill_filter': 'gpt_cc_prospect',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'CC Enchanters v2 Agent'
        },
        'MV_Sales': {
            'bot_skills': ['GPT_MV_PROSPECT'],
            'agent_skills': ['GPT CC Shadowers', 'CHATGPT_SALES_SHADOWERS'],
            'table_name': 'LLM_EVAL.RAW_DATA.MV_SALES_CHATS',
            'skill_filter': 'gpt_mv_prospect',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'MV - Sales - Sally'
        },
        'Delighters': {
            'bot_skills': ['GPT_Delighters'],
            'agent_skills': ['Delighters', 'GPT_DELIGHTERS_SHADOWERS', 'DELIGHTERS'],
            'table_name': 'LLM_EVAL.RAW_DATA.DELIGHTERS_CHATS',
            'skill_filter': 'gpt_delighters',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'Delighters Agent '
        },
        'Doctors': {
            'bot_skills': ['GPT_Doctors'],
            'agent_skills': ['Doctor'],
            'table_name': 'LLM_EVAL.RAW_DATA.DOCTORS_CHATS',
            'skill_filter': 'gpt_doctors',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'Doctor\'s assistant'
        },
        'AT_Filipina': {
            'bot_skills': [
                'GPT_MAIDSAT', 'Filipina_Outside_Not_Interested', 'Filipina_outside_late_joiner',
                'Filipina_Outside_Cancel_Requested', 'Filipina_Outside_Pending_Facephoto',
                'Filipina_Outside_Pending_Passport', 'Filipina_Outside_Pending_Ticket',
                'Filipina_Outside_UAE_Pending_Joining_Date',
                'Filipina_Outside_Ticket_Booked', 'Filipina_in_PHl_Not_valid_OEC_Country',
                'Filipina_in_PHl_Pending_Facephoto', 'Filipina_in_PHl_Pending_OEC_From_Company',
                'Filipina_in_PHl_Pending_OEC_From_maid', 'Filipina_in_PHl_Pending_Passport',
                'Filipina_in_PHl_Pending_Ticket', 'Filipina_in_PHl_Pending_valid_visa',
                'Filipina_in_PHl_Ticket_Booked', 'GPT_MAIDSAT_FILIPINA_PHILIPPINES',
                'GPT_MAIDSAT_FILIPINA_OUTSIDE'
            ],
            'agent_skills': [
                'NUDGERS_REPETITIVE', 'GPT_FILIPINA_SHADOWERS', 'Nudger_TaxiBooking',
                'Nudgers_agents', 'Airport hustlers'
            ],
            'table_name': 'LLM_EVAL.RAW_DATA.APPLICANTS_CHATS',
            'skill_filter': 'filipina_outside',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'Maids Line'
        },
        'AT_African': {
            'bot_skills': [
                'MAIDSAT_AFRICAN_GPT', 'GPT_MAIDSAT_AFRICAN_KENYA', 
                'GPT_MAIDSAT_AFRICAN_OUTSIDE', 'GPT_MAIDSAT_AFRICAN_UAE'
            ],
            'agent_skills': [
                'AFRICAN_NUDGER', 'Kenyan_Attestation_Hustling', 'Kenyan_PreAttestation',
                'Nudgers_Repetitive_Kenyan', 'AFRICAN_NUDGER'
            ],
            'table_name': 'LLM_EVAL.RAW_DATA.APPLICANTS_CHATS',
            'skill_filter': 'maidsat_africa',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'Maids Line'
        },
        'AT_Ethiopian': {
            'bot_skills': [
                'MAIDSAT_ETHIOPIAN_GPT', 'Ethiopian Assessment', 'Ethiopian Passed Question Assessment',
                'Ethiopian Failed Question Assessment', 'Ethiopian Client Scenario', 'Ethiopian Sent video',
                'Ethiopian Failed Client Scenario', 'Ethiopian Applicant Passed Video',
                'Ethiopian Applicant Failed Video', 'Ethiopian Profile Picture Collection',
                'Ethiopian Passport Collection', 'Ethiopian Pending operator visit',
                'Ethiopian OP Assessment', 'Ethiopian OP Passed Questions', 'Ethiopian OP Failed Questions',
                'Ethiopian OP Client Scenario', 'Ethiopian OP Sent Video', 'Ethiopian OP Failed Client Scenario',
                'Ethiopian OP Passed Video', 'Ethiopian OP Failed Video', 'Ethiopian Invalid Passport',
                'Ethiopian LAWP Maids'
            ],
            'agent_skills': [
                'ETHIOPIAN_NUDGER', 'SCREENERS AGENTS'
            ],
            'table_name': 'LLM_EVAL.RAW_DATA.APPLICANTS_CHATS',
            'skill_filter': 'maidsat_ethiopia',
            'bot_filter': 'bot',
            'GPT_AGENT_NAME': 'Maids Line'
        }
    }


def get_llm_prompts_config():
    """
    LLM prompts configuration for each department.
    All departments use SA_PROMPT for sentiment analysis with NPS scoring.
    MV_Resolvers additionally keeps existing client_suspecting_ai prompts in JSON format.
    """
    # Common SA_prompt configuration for all departments
    sa_prompt_config = {
        'prompt': "",
        'system_prompt': SA_PROMPT,  # The detailed SA_PROMPT instructions become the system prompt
        'conversion_type': 'segment',
        'model_type': 'openai',
        'model': 'gpt-4o-mini',
        'temperature': 0,
        'max_tokens': 2048,
        'output_table': 'SA_RAW_DATA'  # Will be set per department below
    }

    client_suspecting_ai_prompt_config = {
        'prompt': "",
        'system_prompt': CLIENT_SUSPECTING_AI_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 7000,
        'output_table': 'CLIENT_SUSPECTING_AI_RAW_DATA'
    }

    legal_alignment_prompt_config = {
        'prompt': "",
        'system_prompt': LEGAL_ALIGNMENT_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 2048,
        'output_table': 'LEGAL_ALIGNMENT_RAW_DATA'
    }

    call_request_prompt_config = {
        'prompt': "",
        'system_prompt': CALL_REQUEST_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 2048,
        'output_table': 'CALL_REQUEST_RAW_DATA'
    }

    categorizing_prompt_config = {
        'prompt': "",
        'system_prompt': CATEGORIZING_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 40000,
        'output_table': 'CATEGORIZING_RAW_DATA'
    }

    false_promises_prompt_config = {
        'prompt': "",
        'system_prompt': FALSE_PROMISES_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 40000,
        'output_table': 'FALSE_PROMISES_RAW_DATA',
        
    }

    ftr_prompt_config = {
        'prompt': "",
        'system_prompt': FTR_PROMPT,
        'conversion_type': 'xml3d',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 20000,
        'output_table': 'FTR_RAW_DATA'
    }

    doctors_categorizing_prompt_config = {
        'prompt': "",
        'system_prompt': DOCTORS_CATEGORIZING_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'gemini',
        'model': 'gemini-2.5-flash',
        'temperature': 0.2,
        'max_tokens': 2048,
        'output_table': 'DOCTORS_CATEGORIZING_RAW_DATA'
    }

    doctors_misprescription_prompt_config = {
        'prompt': "",
        'system_prompt': DOCTORS_MISPRESCRIPTION_PROMPT,
        'conversion_type': 'json',
        'model_type': 'gemini',
        'model': 'gemini-2.5-flash',
        'temperature': 0.2,
        'max_tokens': 7000,
        'output_table': 'DOCTORS_MISPRESCRIPTION_RAW_DATA'
    }

    doctors_unnecessary_clinic_prompt_config = {
        'prompt': "",
        'system_prompt': DOCTORS_UNNECESSARY_CLINIC_PROMPT,
        'conversion_type': 'json',
        'model_type': 'gemini',
        'model': 'gemini-2.5-flash',
        'temperature': 0.2,
        'max_tokens': 7000,
        'output_table': 'DOCTORS_UNNECESSARY_CLINIC_RAW_DATA'
    }

    clarity_score_prompt_config = {
        'prompt': "",
        'system_prompt': CLARITY_SCORE_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 10000,
        'output_table': 'CLARITY_SCORE_RAW_DATA'
    }

    policy_escalation_prompt_config = {
        'prompt': "",
        'system_prompt': POLICY_ESCALATION_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 30000,
        'output_table': 'POLICY_ESCALATION_RAW_DATA'
    }

    threatening_prompt_config = {
        'prompt': "",
        'system_prompt': THREATINING_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 2048,
        'output_table': 'THREATENING_RAW_DATA'
    }

    loss_interest_prompt_config = {
        'prompt': "",
        'system_prompt': {
            "Filipina_Outside_Pending_Facephoto": LOSS_INTEREST_OUTSIDE_PROFILE_PROMPT, 
            "Filipina_Outside_Pending_Passport": LOSS_INTEREST_OUTSIDE_PASSPORT_PROMPT, 
            "Filipina_Outside_UAE_Pending_Joining_Date": LOSS_INTEREST_EXPECTED_DTJ_PROMPT, 
            "Filipina_in_PHl_Pending_valid_visa": LOSS_INTEREST_ACTIVE_VISA_PROMPT, 
            "Filipina_in_PHL_Pending_Passport": LOSS_INTEREST_PHL_PASSPORT_PROMPT,
            "Filipina_in_PHl_Pending_Facephoto": LOSS_INTEREST_PHL_PROFILE_PROMPT,
            "Filipina_in_PHl_Pending_OEC_From_Company": LOSS_INTEREST_OEC_PROMPT, 
            "Filipina_in_PHl_Pending_OEC_From_maid": LOSS_INTEREST_OEC_PROMPT},
        'conversion_type': 'xml',
        'model_type': 'gemini',
        'model': 'gemini-2.5-pro',
        'temperature': 0.2,
        'max_tokens': 20000,
        'output_table': 'LOSS_INTEREST_RAW_DATA'
    }

    intervention_prompt_config = {
        'prompt': "",
        'system_prompt': INTERVENTION_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'gemini',
        'model': 'gemini-2.5-pro',
        'temperature': 0,
        'max_tokens': 10000,
        'output_table': 'CATEGORIZING_RAW_DATA'
    }

    clinic_recommendation_reason_prompt_config = {
        'prompt': "",
        'system_prompt': CLINIC_RECOMMENDATION_REASON_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'gemini',
        'model': 'gemini-2.5-pro',
        'temperature': 0.2,
        'max_tokens': 7000,
        'output_table': 'CLINIC_RECOMMENDATION_REASON_RAW_DATA'
    }

    missing_policy_prompt_config = {
        'prompt': "",
        'system_prompt': MISSING_POLICY_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0,
        'max_tokens': 30000,
        'output_table': 'MISSING_POLICY_RAW_DATA'
    }

    unclear_policy_prompt_config = {
        'prompt': "",
        'system_prompt': UNCLEAR_POLICY_PROMPT,
        'conversion_type': 'json',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0,
        'max_tokens': 30000,
        'output_table': 'UNCLEAR_POLICY_RAW_DATA'
    }

    policy_violation_prompt_config = {
        'prompt': "",
        'system_prompt': AT_FILIPINA_POLICY_VIOLATION_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'gemini',
        'model': 'gemini-2.5-pro',
        'temperature': 1,
        'max_tokens': 30000,
        'output_table': 'POLICY_VIOLATION_RAW_DATA'
    }

    sales_transfer_escalation_prompt_config = {
        'prompt': "",
        'system_prompt': SALES_TRANSFER_ESCALATION_PROMPT,
        'conversion_type': 'json',
        'model_type': 'openai',
        'model': 'gpt-5-mini',
        'temperature': 0.2,
        'max_tokens': 2048,
        'output_table': 'TRANSFER_ESCALATION_RAW_DATA'
    }

    sales_transfer_known_flow_prompt_config = {
        'prompt': "",
        'system_prompt': SALES_TRANSFER_KNOWN_FLOW_PROMPT,
        'conversion_type': 'json',
        'model_type': 'openai',
        'model': 'gpt-5-mini',
        'temperature': 0.2,
        'max_tokens': 2048,
        'output_table': 'TRANSFER_KNOWN_FLOW_RAW_DATA'
    }

    mv_resolvers_wrong_tool_prompt_config = {
        'prompt': "",
        'system_prompt': MV_RESOLVERS_WRONG_TOOL_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 30000,
        'output_table': 'WRONG_TOOL_RAW_DATA'
    }

    mv_resolvers_missing_tool_prompt_config = {
        'prompt': "",
        'system_prompt': MV_RESOLVERS_MISSING_TOOL_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5',
        'temperature': 0.2,
        'max_tokens': 30000,
        'output_table': 'MISSING_TOOL_RAW_DATA'
    }

    tool_prompt_config = {
        'prompt': "",
        'system_prompt': DOCTORS_TOOL_PROMPT,
        'conversion_type': 'json',
        'model_type': 'gemini',
        'model': 'gemini-2.5-pro',
        'temperature': 0.2,
        'max_tokens': 30000,
        'output_table': 'TOOL_RAW_DATA'
    }

    cc_sales_policy_violation_prompt_config = {
        'prompt': "",
        'system_prompt': CC_SALES_POLICY_VIOLATION_PROMPT,
        'conversion_type': 'xml',
        'model_type': 'openai',
        'model': 'gpt-5-mini',
        'temperature': 0.2,
        'max_tokens': 30000,
        'output_table': 'POLICY_VIOLATION_RAW_DATA'
    }

    return {
        'CC_Resolvers': {
            'SA_prompt': sa_prompt_config,
        },
        'MV_Resolvers': {
            'SA_prompt': {**sa_prompt_config, 'model': 'gpt-5', 'conversion_type': 'xml'},
            'client_suspecting_ai': client_suspecting_ai_prompt_config,
            'legal_alignment': legal_alignment_prompt_config,
            'call_request': call_request_prompt_config,
            'categorizing': categorizing_prompt_config,
            'false_promises': false_promises_prompt_config,
            "ftr": ftr_prompt_config,
            "threatening": threatening_prompt_config,
            "policy_escalation": policy_escalation_prompt_config,
            "clarity_score": clarity_score_prompt_config,
            "missing_policy": missing_policy_prompt_config,
            "unclear_policy": unclear_policy_prompt_config,
            "mv_resolvers_wrong_tool": mv_resolvers_wrong_tool_prompt_config,
            "mv_resolvers_missing_tool": mv_resolvers_missing_tool_prompt_config
        },
        'Doctors': {
            'SA_prompt': sa_prompt_config,
            'doctors_categorizing': doctors_categorizing_prompt_config,
            'misprescription': doctors_misprescription_prompt_config,
            'unnecessary_clinic': doctors_unnecessary_clinic_prompt_config,
            # Override model to gemini-2.5-flash for these three prompt types only for Doctors
            'clarity_score': { **clarity_score_prompt_config, 'model': 'gemini-2.5-flash', 'model_type': 'gemini' },
            'policy_escalation': { **policy_escalation_prompt_config, 'model': 'gemini-2.5-flash', 'model_type': 'gemini' },
            'client_suspecting_ai': { **client_suspecting_ai_prompt_config, 'model': 'gemini-2.5-flash', 'model_type': 'gemini' },
            'intervention': intervention_prompt_config,
            'clinic_recommendation_reason': clinic_recommendation_reason_prompt_config,
            'tool': tool_prompt_config
        },
        'Delighters': {
            'SA_prompt': sa_prompt_config,
        },
        'AT_Filipina': {
            'SA_prompt': sa_prompt_config,
            'loss_interest': loss_interest_prompt_config,
            'policy_violation': policy_violation_prompt_config,
            'tool': {**tool_prompt_config, 'system_prompt': AT_FILIPINA_TOOL_PROMPT}
        },
        'AT_African': {
            'SA_prompt': sa_prompt_config,
        },
        'AT_Ethiopian': {
            'SA_prompt': sa_prompt_config,
        },
        'CC_Sales': {
            'SA_prompt': sa_prompt_config,
            'client_suspecting_ai': { **client_suspecting_ai_prompt_config, 'system_prompt': SALES_CLIENT_SUSPECTING_AI_PROMPT, 'model': 'gemini-2.5-flash', 'model_type': 'gemini' },
            'clarity_score': { **clarity_score_prompt_config, 'system_prompt': SALES_CLARITY_SCORE_PROMPT, 'model': 'gemini-2.5-flash', 'model_type': 'gemini' },
            'sales_transfer_escalation': sales_transfer_escalation_prompt_config,
            'sales_transfer_known_flow': sales_transfer_known_flow_prompt_config,
            'tool': {**tool_prompt_config, 'system_prompt': CC_SALES_TOOL_PROMPT},
            'policy_violation': cc_sales_policy_violation_prompt_config
        },
        'MV_Sales': {
            'SA_prompt': sa_prompt_config,
            'client_suspecting_ai': { **client_suspecting_ai_prompt_config, 'system_prompt': SALES_CLIENT_SUSPECTING_AI_PROMPT, 'model': 'gemini-2.5-flash', 'model_type': 'gemini' },
            'clarity_score': { **clarity_score_prompt_config, 'system_prompt': SALES_CLARITY_SCORE_PROMPT, 'model': 'gemini-2.5-flash', 'model_type': 'gemini' },
        }
    }


def get_snowflake_llm_departments_config():
    """
    Combined configuration: base department config + LLM prompts
    """
    base_config = get_snowflake_base_departments_config()
    llm_prompts = get_llm_prompts_config()
    
    # Merge configurations
    llm_config = {}
    for dept_name, base_dept_config in base_config.items():
        llm_config[dept_name] = {
            **base_dept_config,
            'llm_prompts': llm_prompts.get(dept_name, {})
        }
    
    return llm_config


def get_department_prompt_types(department_name):
    """
    Get all available prompt types for a specific department
    """
    config = get_llm_prompts_config()
    return list(config.get(department_name, {}).keys())


def get_prompt_config(department_name, prompt_type):
    """
    Get specific prompt configuration
    """
    config = get_llm_prompts_config()
    return config.get(department_name, {}).get(prompt_type, None)


def list_all_departments():
    """
    Get list of all configured departments
    """
    return list(get_snowflake_base_departments_config().keys())


def list_all_output_tables():
    """
    Get list of all LLM output tables across all departments
    """
    tables = []
    prompts_config = get_llm_prompts_config()
    
    for dept_name, dept_prompts in prompts_config.items():
        for prompt_type, prompt_config in dept_prompts.items():
            tables.append(prompt_config['output_table'])
    
    return sorted(list(set(tables)))  # Remove duplicates and sort


def get_metrics_configuration():
    """
    Define metrics calculation mapping per department
    Maps departments to their specific metrics calculations and master tables
    """
    
    return {
        'MV_Resolvers': {
            'master_table': 'MV_RESOLVERS_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                },
                'client_suspecting_ai': {
                    'function': calculate_client_suspecting_ai_percentage,
                    'columns': ['CLIENT_SUSPECTING_AI_PERCENTAGE', 'CLIENT_SUSPECTING_AI_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['client_suspecting_ai'],
                    'order': 2
                },
                'legal_metrics': {
                    'function': calculate_legal_metrics,
                    'columns': ['ESCALATION_RATE', 'LEGAL_CONCERNS_PERCENTAGE', 'LEGAL_ALIGNMENT_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['legal_alignment'],
                    'order': 3
                },
                'call_request_metrics': {
                    'function': calculate_call_request_metrics,
                    'columns': ['CALL_REQUEST_RATE', 'CALL_REQUEST_COUNT', 'CALL_REQUEST_ANALYSIS_SUMMARY', 'REBUTTAL_RESULT_RATE', 'NO_RETENTION_COUNT'],
                    'depends_on_prompts': ['call_request'],
                    'order': 4
                },
                'intervention_transfer': {
                    'function': calculate_overall_percentages,
                    'columns': ['INTERVENTION_PERCENTAGE', 'TRANSFER_PERCENTAGE', 'INTERVENTION_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['categorizing'],
                    'order': 5
                },
                'false_promises': {
                    'function': calculate_false_promises_percentage,
                    'columns': ['FALSE_PROMISES_PERCENTAGE', 'FALSE_PROMISES_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['false_promises'],
                    'order': 6
                },
                'ftr': {
                    'function': calculate_ftr_percentage,
                    'columns': ['FTR_PERCENTAGE', 'FTR_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['ftr'],
                    'order': 7
                },
                'threatening': {
                    'function': calculate_threatening_percentage,
                    'columns': ['THREATENING_PERCENTAGE', 'THREATENING_COUNT', 'THREATENING_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['threatening'],
                    'order': 8
                },
                'policy_escalation': {
                    'function': calculate_policy_escalation_percentage,
                    'columns': ['POLICY_ESCALATION_PERCENTAGE', 'POLICY_ESCALATION_COUNT', 'POLICY_ESCALATION_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['policy_escalation'],
                    'order': 9
                },
                'clarity_score': {
                    'function': calculate_clarity_score_percentage,
                    'columns': ['CLARITY_SCORE_PERCENTAGE', 'CLARITY_SCORE_COUNT', 'CLARITY_SCORE_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['clarity_score'],
                    'order': 10
                },
                'system_prompt_token_count': {
                    'function': create_system_prompt_token_summary_report,
                    'columns': ['SYSTEM_PROMPT_TOKEN_COUNT'],
                    'depends_on_prompts': ['policy_escalation'],
                    'order': 11
                },
                'mv_resolvers_wrong_tool': {
                    'function': generate_mv_resolvers_wrong_tool_summary_report,
                    'columns': ['WRONG_TOOL_PERCENTAGE', 'WRONG_TOOL_COUNT', 'WRONG_TOOL_ANALYSIS_SUMMARY', 'WRONG_TOOL_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['mv_resolvers_wrong_tool'],
                    'order': 12
                },
                'mv_resolvers_missing_tool': {
                    'function': generate_mv_resolvers_missing_tool_summary_report,
                    'columns': ['MISSING_TOOL_PERCENTAGE', 'MISSING_TOOL_COUNT', 'MISSING_TOOL_ANALYSIS_SUMMARY', 'MISSING_TOOL_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['mv_resolvers_missing_tool'],
                    'order': 13
                },
                'shadowing_automation_summary': {
                    'function': create_shadowing_automation_summary_report,
                    'columns': ['SHADOWING_AUTOMATION_ANALYSIS_SUMMARY','SHADOWING_AUTOMATION_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 14
                },
                'missing_policy': {
                    'function': calculate_missing_policy_metrics,
                    'columns': ['MISSING_POLICY_PERCENTAGE', 'MISSING_POLICY_COUNT', 'MISSING_POLICY_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['missing_policy'],
                    'order': 15
                },
                'unclear_policy': {
                    'function': calculate_unclear_policy_metrics,
                    'columns': ['UNCLEAR_POLICY_PERCENTAGE', 'UNCLEAR_POLICY_COUNT', 'UNCLEAR_POLICY_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['unclear_policy'],
                    'order': 16
                }
            }
        },
        'CC_Resolvers': {
            'master_table': 'CC_RESOLVERS_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                }
            }
        },
        'Doctors': {
            'master_table': 'DOCTORS_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                },
                'misprescription': {
                    'function': calculate_misprescription_percentage,
                    'columns': ['MISPRESCRIPTION_PERCENTAGE', 'MISPRESCRIPTION_COUNT', 'MISPRESCRIPTION_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['misprescription'],
                    'order': 2
                },
                'unnecessary_clinic': {
                    'function': calculate_unnecessary_clinic_percentage,
                    'columns': ['UNNECESSARY_CLINIC_PERCENTAGE', 'COULD_AVOID_COUNT', 'UNNECESSARY_CLINIC_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['unnecessary_clinic'],
                    'order': 3
                },
                'clarity_score': {
                    'function': calculate_clarity_score_percentage,
                    'columns': ['CLARITY_SCORE_PERCENTAGE', 'CLARITY_SCORE_COUNT', 'CLARITY_SCORE_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['clarity_score'],
                    'order': 4
                },
                'categorizing_summary': {
                    'function': create_doctors_categorizing_summary_report,
                    'columns': ['CATEGORIZING_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['doctors_categorizing'],
                    'order': 5
                },
                'policy_escalation': {
                    'function': calculate_policy_escalation_percentage,
                    'columns': ['POLICY_ESCALATION_PERCENTAGE', 'POLICY_ESCALATION_COUNT', 'POLICY_ESCALATION_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['policy_escalation'],
                    'order': 6
                },
                'client_suspecting_ai': {
                    'function': calculate_client_suspecting_ai_percentage,
                    'columns': ['CLIENT_SUSPECTING_AI_PERCENTAGE', 'CLIENT_SUSPECTING_AI_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['client_suspecting_ai'],
                    'order': 7
                },
                'system_prompt_token_count': {
                    'function': create_system_prompt_token_summary_report,
                    'columns': ['SYSTEM_PROMPT_TOKEN_COUNT'],
                    'depends_on_prompts': ['policy_escalation'],
                    'order': 8
                },
                'intervention_transfer': {
                    'function': calculate_overall_percentages,
                    'columns': ['INTERVENTION_PERCENTAGE', 'TRANSFER_PERCENTAGE', 'INTERVENTION_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['intervention'],
                    'order': 9
                },
                'clinic_recommendation_reason': {
                    'function': create_clinic_reasons_summary_report,
                    'columns': ['CLINIC_RECOMMENDATION_REASON_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['clinic_recommendation_reason'],
                    'order': 10
                },
                'tool': {
                    'function': generate_tool_summary_report,
                    'columns': ['WRONG_TOOL_PERCENTAGE', 'WRONG_TOOL_COUNT', 'MISSING_TOOL_PERCENTAGE', 'MISSING_TOOL_COUNT', 'TOOL_ANALYSIS_SUMMARY', 'TOOL_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['tool'],
                    'order': 11
                }
            }
        },
        'Delighters': {
            'master_table': 'DELIGHTERS_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                }
            }
        },
        'AT_Filipina': {
            'master_table': 'AT_FILIPINA_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                },
                'loss_interest': {
                    'function': create_loss_interest_summary_report,
                    'columns': ['LOSS_INTEREST_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['loss_interest'],
                    'order': 2
                },
                'policy_violation': {
                    'function': calculate_policy_violation_metrics,
                    'columns': ['A_MISSING_POLICY_PERCENTAGE', 'B_MISSING_POLICY_PERCENTAGE', 'A_UNCLEAR_POLICY_PERCENTAGE', 'B_UNCLEAR_POLICY_PERCENTAGE', 'A_WRONG_POLICY_PERCENTAGE', 'B_WRONG_POLICY_PERCENTAGE', 'POLICY_VIOLATION_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['policy_violation'],
                    'order': 3
                },
                'system_prompt_token_count': {
                    'function': create_system_prompt_token_summary_report,
                    'columns': ['SYSTEM_PROMPT_TOKEN_COUNT'],
                    'depends_on_prompts': ['policy_violation'],
                    'order': 4
                },
                'tool': {
                    'function': generate_at_filipina_tool_summary_report,
                    'columns': ['WRONG_TOOL_PERCENTAGE', 'FALSE_TRIGGER_COUNT', 'MISSING_TOOL_PERCENTAGE', 'MISSING_TRIGGER_COUNT', 'TOOL_ANALYSIS_SUMMARY', 'TOOL_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['tool'],
                    'order': 5
                }
            }
        },
        'AT_African': {
            'master_table': 'AT_AFRICAN_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                }
            }
        },
        'AT_Ethiopian': {
            'master_table': 'AT_ETHIOPIAN_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                }
            }
        },
        'CC_Sales': {
            'master_table': 'CC_SALES_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                },
                'client_suspecting_ai': {
                    'function': calculate_client_suspecting_ai_percentage,
                    'columns': ['CLIENT_SUSPECTING_AI_PERCENTAGE', 'CLIENT_SUSPECTING_AI_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['client_suspecting_ai'],
                    'order': 2
                },
                'clarity_score': {
                    'function': calculate_clarity_score_percentage,
                    'columns': ['CLARITY_SCORE_PERCENTAGE', 'CLARITY_SCORE_COUNT', 'CLARITY_SCORE_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['clarity_score'],
                    'order': 3
                },
                'sales_transfer_escalation': {
                    'function': calculate_transer_escalation_percentage,
                    'columns': ['TRANSFER_ESCALATION_PERCENTAGE_A', 'TRANSFER_ESCALATION_PERCENTAGE_B', 'TRANSFER_ESCALATION_COUNT', 'TRANSFER_ESCALATION_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['sales_transfer_escalation'],
                    'order': 4
                },
                'sales_transfer_known_flow': {
                    'function': calculate_transer_known_flow_percentage,
                    'columns': ['TRANSFER_KNOWN_FLOW_PERCENTAGE_A', 'TRANSFER_KNOWN_FLOW_PERCENTAGE_B', 'TRANSFER_KNOWN_FLOW_COUNT', 'TRANSFER_KNOWN_FLOW_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['sales_transfer_known_flow'],
                    'order': 5
                },
                'tool': {
                    'function': generate_tool_summary_report,
                    'columns': ['WRONG_TOOL_PERCENTAGE', 'WRONG_TOOL_COUNT', 'MISSING_TOOL_PERCENTAGE', 'MISSING_TOOL_COUNT', 'TOOL_ANALYSIS_SUMMARY', 'TOOL_SUMMARY_SUCCESS'],
                    'depends_on_prompts': ['tool'],
                    'order': 6
                },
                'policy_violation': {
                    'function': calculate_cc_sales_policy_violation_metrics,
                    'columns': ['MISSING_POLICY_PERCENTAGE', 'MISSING_POLICY_COUNT', 'UNCLEAR_POLICY_PERCENTAGE', 'UNCLEAR_POLICY_COUNT', 'POLICY_VIOLATION_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['policy_violation'],
                    'order': 7
                }
            }
        },
        'MV_Sales': {
            'master_table': 'MV_SALES_SUMMARY',
            'metrics': {
                'weighted_nps': {
                    'function': calculate_weighted_nps_per_department,
                    'columns': ['WEIGHTED_AVG_NPS', 'WEIGHTED_AVG_NPS_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['SA_prompt'],
                    'order': 1
                },
                'client_suspecting_ai': {
                    'function': calculate_client_suspecting_ai_percentage,
                    'columns': ['CLIENT_SUSPECTING_AI_PERCENTAGE', 'CLIENT_SUSPECTING_AI_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['client_suspecting_ai'],
                    'order': 2
                },
                'clarity_score': {
                    'function': calculate_clarity_score_percentage,
                    'columns': ['CLARITY_SCORE_PERCENTAGE', 'CLARITY_SCORE_COUNT', 'CLARITY_SCORE_ANALYSIS_SUMMARY'],
                    'depends_on_prompts': ['clarity_score'],
                    'order': 3
                }
            }
        }
    }


def get_department_summary_schema(department_name):
    """
    Generate dynamic table schema based on department's metrics configuration
    
    Args:
        department_name: Department name to get schema for
    
    Returns:
        Dictionary of column_name: data_type for CREATE TABLE
    """
    base_columns = {
        'DATE': 'DATE',
        'DEPARTMENT': 'VARCHAR(100)',
        'TIMESTAMP': 'TIMESTAMP'
    }
    
    metrics_config = get_metrics_configuration()
    dept_config = metrics_config.get(department_name, {})
    dept_metrics = dept_config.get('metrics', {})
    
    # Add metric columns (all metrics are numeric)
    metric_columns = {}
    for metric_name, metric_config in dept_metrics.items():
        for col in metric_config['columns']:
            metric_columns[col] = 'FLOAT'
    
    return {**base_columns, **metric_columns}


def list_all_master_tables():
    """
    Get list of all department master summary tables
    """
    tables = []
    metrics_config = get_metrics_configuration()
    
    for dept_name, dept_config in metrics_config.items():
        tables.append(dept_config['master_table'])
    
    return sorted(list(set(tables)))  # Remove duplicates and sort
