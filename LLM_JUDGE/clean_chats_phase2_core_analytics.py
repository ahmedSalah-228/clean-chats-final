# Phase 2: Core Analytics - Snowflake Migration
# Bot Handling Analysis & Repetition Analysis
# Adapted from main_analytics.py for Snowflake integration
# STANDALONE VERSION - All Phase 1 functions included

import snowflake.snowpark as snowpark
from snowflake.snowpark.functions import col, current_timestamp, lit
import pandas as pd
from datetime import datetime, timedelta
import traceback
import numpy as np
import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from itertools import combinations

# ============================================================================
# PHASE 1 FOUNDATION FUNCTIONS (INCLUDED FOR STANDALONE EXECUTION)
# ============================================================================

def infer_tool_message_type(text_value, department_name=None):
    """
    Inspect TEXT field (string or dict) and infer if it's a tool or tool response message.
    Criteria:
    - Must parse to a dict and contain a 'content' object
    - If it has 'tool_calls' -> return 'tool'
    - If it has 'tool_call_id' -> return 'tool response'
    Returns 'tool' | 'tool response' | None
    """
    try:
        parsed = None
        if isinstance(text_value, dict):
            parsed = text_value
        elif isinstance(text_value, str):
            text_str = text_value.strip()
            if text_str.startswith('{') and text_str.endswith('}'):
                # Attempt strict JSON parse; if it fails, remove trailing commas before } or ] and retry
                try:
                    parsed = json.loads(text_str)
                except Exception:
                    cleaned_str = re.sub(r',\s*([}\]])', r'\1', text_str)
                    try:
                        parsed = json.loads(cleaned_str)
                    except Exception:
                        return None
        if not isinstance(parsed, dict):
            return None

        # General detection first (top-level)
        if parsed.get('tool_calls'):
            return 'tool'
        if parsed.get('tool_call_id'):
            return 'tool response'

        # Also check inside content if it's a dict
        content_obj = parsed.get('content')
        if isinstance(content_obj, dict):
            if content_obj.get('tool_calls'):
                return 'tool'
            if content_obj.get('tool_call_id'):
                return 'tool response'

        # Fallback: detect messages shaped like {"name": <str>, "arguments": { ... }}
        name_exists = 'name' in parsed and isinstance(parsed.get('name'), str) and parsed.get('name')
        arguments_obj = parsed.get('arguments')
        arguments_is_object = isinstance(arguments_obj, dict)
        if name_exists and arguments_is_object:
            return 'tool'

        return None
    except Exception:
        return None

def format_error_details(e, context=""):
    """
    Format exception details for comprehensive error reporting.
    
    Args:
        e: Exception object
        context: Additional context about where the error occurred
    
    Returns:
        Formatted error string with full details
    """
    error_details = traceback.format_exc()
    return f"""
{'=' * 50}
🚨 ERROR DETAILS {f"- {context}" if context else ""}
{'=' * 50}
Error Type: {type(e).__name__}
Error Message: {str(e)}

Full Traceback:
{error_details}
{'=' * 50}
"""

def get_snowflake_departments_config():
    """
    Department configuration adapted from main_analytics.py for Snowflake.
    Maps department names to their bot_skills, agent_skills, and Snowflake table names.
    """
    return {
        'CC_Resolvers': {
            'bot_skills': ['GPT_CC_RESOLVERS'],
            'agent_skills': ['CC_RESOLVERS_AGENTS', 'DDC_AGENTS', 'GPT CC Shadowers'],
            'table_name': 'LLM_EVAL.RAW_DATA.CC_CLIENT_CHATS',  # Update with actual table name
            'skill_filter': 'gpt_cc_resolvers',  # For compatibility with existing logic
            'bot_filter': 'bot'
        },
        'MV_Resolvers': {
            'bot_skills': ['GPT_MV_RESOLVERS'],
            'agent_skills': ['MV_RESOLVERS_SENIORS', 'MV_CALLERS', 'MV_RESOLVERS_MANAGER', 
                           'GPT_MV_RESOLVERS_SHADOWERS', 'GPT_MV_RESOLVERS_SHADOWERS_MANAGER'],
            'table_name': 'LLM_EVAL.RAW_DATA.MV_CLIENT_CHATS',  # Update with actual table name
            'skill_filter': 'gpt_mv_resolvers',
            'bot_filter': 'bot'
        },
        'CC_Sales': {
            'bot_skills': ['GPT_CC_PROSPECT'],
            'agent_skills': ['GPT CC Shadowers', 'CHATGPT_SALES_SHADOWERS'],
            'table_name': 'LLM_EVAL.RAW_DATA.CC_SALES_CHATS',  # Update with actual table name
            'skill_filter': 'gpt_cc_prospect',
            'bot_filter': 'bot'
        },
        'MV_Sales': {
            'bot_skills': ['GPT_MV_PROSPECT'],
            'agent_skills': ['GPT CC Shadowers', 'CHATGPT_SALES_SHADOWERS'],
            'table_name': 'LLM_EVAL.RAW_DATA.MV_SALES_CHATS',  # Update with actual table name
            'skill_filter': 'gpt_mv_prospect',
            'bot_filter': 'bot'
        },
        'Delighters': {
            'bot_skills': ['GPT_Delighters'],
            'agent_skills': ['Delighters', 'GPT_DELIGHTERS_SHADOWERS', 'DELIGHTERS'],
            'table_name': 'LLM_EVAL.RAW_DATA.DELIGHTERS_CHATS',  # Update with actual table name
            'skill_filter': 'gpt_delighters',
            'bot_filter': 'bot'
        },
        'Doctors': {
            'bot_skills': ['GPT_Doctors'],
            'agent_skills': ['Doctor'],
            'table_name': 'LLM_EVAL.RAW_DATA.DOCTORS_CHATS',  # Update with actual table name
            'skill_filter': 'gpt_doctors',
            'bot_filter': 'bot'
        },
        'AT_Filipina': {
            'bot_skills': [
                'GPT_MAIDSAT', 'Filipina_Outside_Not_Interested', 'Filipina_outside_late_joiner',
                'Filipina_Outside_Cancel_Requested', 'Filipina_Outside_Pending_Facephoto',
                'Filipina_Outside_Pending_Passport', 'Filipina_Outside_Pending_Ticket',
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
            'table_name': 'LLM_EVAL.RAW_DATA.APPLICANTS_CHATS',  # Shared table
            'skill_filter': 'filipina_outside',
            'bot_filter': 'bot'
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
            'table_name': 'LLM_EVAL.RAW_DATA.APPLICANTS_CHATS',  # Shared table
            'skill_filter': 'maidsat_africa',
            'bot_filter': 'bot'
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
            'table_name': 'LLM_EVAL.RAW_DATA.APPLICANTS_CHATS',  # Shared table
            'skill_filter': 'maidsat_ethiopia',
            'bot_filter': 'bot'
        }
    }


def create_snowflake_date_range(target_date=None):
    """
    Create date range for Snowflake filtering.
    Adapted from main_analytics.py create_date_range() function.
    Collects data from target_date-2 to target_date-1 (2 days of data).
    """
    if target_date is None:
        target_date = datetime.now()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d')
    
    # Collect data from 2 days before target_date to 1 day before target_date
    start_date = target_date - timedelta(days=1)
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date.replace(hour=23, minute=59, second=59) + timedelta(days=1)
    
    return {
        'start': start_date.strftime('%Y-%m-%d %H:%M:%S'),
        'end': end_date.strftime('%Y-%m-%d %H:%M:%S'),
        'day1_date': start_date.date(),
        'day2_date': (start_date + timedelta(days=1)).date(),
        'yesterday_date': (target_date - timedelta(days=0)).strftime('%Y-%m-%d')
    }


def preprocess_data_snowflake_phase1(df, department_name, target_date=None):
    """
    Phase 1 preprocessing: Basic data cleaning and date filtering for Snowflake.
    Adapted from main_analytics.py preprocessing logic.
    
    Args:
        df: Raw DataFrame from Snowflake table
        department_name: Department name for filtering
        target_date: Target date for analysis
    
    Returns:
        Preprocessed DataFrame
    """
    print(f"  📋 Phase 1 preprocessing for {department_name}...")
    
    
    # Ensure required columns exist and handle missing values
    required_columns = ['CONVERSATION_ID', 'MESSAGE_SENT_TIME', 'MESSAGE_TYPE', 'SENT_BY', 'TARGET_SKILL_PER_MESSAGE']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        print(f"    ❌ MISSING COLUMNS in {department_name}: {missing_columns}")
        return pd.DataFrame()  # Return empty DataFrame if critical columns missing
    
    # Convert MESSAGE_SENT_TIME to datetime
    df['MESSAGE_SENT_TIME'] = pd.to_datetime(df['MESSAGE_SENT_TIME'])
    
    # Sort by conversation ID and message sent time (critical for proper analysis)
    df = df.sort_values(by=['CONVERSATION_ID', 'MESSAGE_SENT_TIME'])
    
    # Drop duplicates based on conversation ID, message sent time, and text content
    original_count = len(df)
    df = df.drop_duplicates(subset=['CONVERSATION_ID', 'MESSAGE_SENT_TIME', 'TEXT'], keep='first')
    if len(df) < original_count:
        print(f"    🧹 Removed {original_count - len(df)} duplicate rows")
    
    # Clean and standardize text fields
    for col in ['MESSAGE_TYPE', 'SENT_BY', 'TARGET_SKILL_PER_MESSAGE']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    
    print(f"    ✅ Preprocessing complete: {len(df)} rows, {df['CONVERSATION_ID'].nunique()} conversations")
    
    return df


def filter_conversations_snowflake_engagement(df, department_name, departments_config, apply_filter_5=True):
    """
    Apply engagement filtering for Snowflake data.
    Adapted from main_analytics.py filter_conversations_combined() function.
    
    Engagement criteria:
    1. Conversation must have at least one consumer normal message
    2. Conversation must have at least one agent/bot normal message from the department
    
    Args:
        df: Preprocessed DataFrame
        department_name: Department name
        departments_config: Department configuration dictionary
    
    Returns:
        Tuple: (filtered_df, filtering_stats)
    """
    print(f"  🔍 Applying engagement filtering for {department_name}...")
    
    if department_name not in departments_config:
        raise ValueError(f"Department '{department_name}' not configured")
    
    dept_config = departments_config[department_name]
    agent_skills = dept_config['agent_skills']
    bot_skills = dept_config['bot_skills']
    
    # Get all unique conversation IDs
    all_conversations = set(df['CONVERSATION_ID'].unique())
    print(f"    📊 Total conversations: {len(all_conversations)}")
    
    # Filter 1: Conversations with consumer normal messages
    consumer_normal_messages = df[
        (df['MESSAGE_TYPE'].str.lower() == 'normal message') &
        (df['SENT_BY'].str.lower() == 'consumer')
    ]
    conversations_with_consumer = set(consumer_normal_messages['CONVERSATION_ID'].unique())
    print(f"    👤 Conversations with consumer messages: {len(conversations_with_consumer)}")
    
    # Filter 2: Conversations with agent normal messages from department
    agent_normal_messages = df[
        (df['MESSAGE_TYPE'].str.lower() == 'normal message') &
        (df['SENT_BY'].str.lower() == 'agent') &
        (df['TARGET_SKILL_PER_MESSAGE'].isin(agent_skills))
    ]
    conversations_with_agents = set(agent_normal_messages['CONVERSATION_ID'].unique())
    print(f"    👨‍💼 Conversations with department agent messages: {len(conversations_with_agents)}")
    
    # Remove N8N_TEST from conversations_with_agents using TARGET_SKILL_PER_MESSAGE
    conversations_with_agents = conversations_with_agents - set(df[df['TARGET_SKILL_PER_MESSAGE'].str.contains('N8N_TEST', na=False, case=False)]['CONVERSATION_ID'].unique())
    print(f"    👨‍💼 Conversations with department agents after removing N8N_TEST: {len(conversations_with_agents)}")
    # Remove N8N_TEST from conversations_with_agents using THROUGH_SKILL
    conversations_with_agents = conversations_with_agents - set(df[df['THROUGH_SKILL'].str.contains('N8N_TEST', na=False, case=False)]['CONVERSATION_ID'].unique())
    print(f"    👨‍💼 Conversations with department agents after removing N8N_TEST through_skill: {len(conversations_with_agents)}")
    
    # Filter 3: Conversations with bot normal messages from department
    bot_normal_messages = df[
        (df['MESSAGE_TYPE'].str.lower() == 'normal message') &
        (df['SENT_BY'].str.lower() == 'bot') &
        (df['TARGET_SKILL_PER_MESSAGE'].isin(bot_skills))
    ]
    conversations_with_bots = set(bot_normal_messages['CONVERSATION_ID'].unique())
    print(f"    🤖 Conversations with department bot messages: {len(conversations_with_bots)}")
    
    # Combine agent and bot conversations
    conversations_with_service = conversations_with_agents.union(conversations_with_bots)
    print(f"    🏢 Conversations with department service: {len(conversations_with_service)}")

    # Remove N8N_TEST from conversations_with_service using both TARGET_SKILL_PER_MESSAGE and THROUGH_SKILL
    conversations_with_service = conversations_with_service - set(df[df['TARGET_SKILL_PER_MESSAGE'].str.contains('N8N_TEST', na=False, case=False)]['CONVERSATION_ID'].unique())
    conversations_with_service = conversations_with_service - set(df[df['THROUGH_SKILL'].str.contains('N8N_TEST', na=False, case=False)]['CONVERSATION_ID'].unique())
    print(f"    🏢 Conversations with department service after removing N8N_TEST: {len(conversations_with_service)}")

    # also do the same for conversations_with_bots
    conversations_with_bots = conversations_with_bots - set(df[df['TARGET_SKILL_PER_MESSAGE'].str.contains('N8N_TEST', na=False, case=False)]['CONVERSATION_ID'].unique())
    print(f"    🏢 Conversations with department bots after removing N8N_TEST: {len(conversations_with_bots)}")
    # also the same for conversations_with_bots but using 'through_skill' instead of 'TARGET_SKILL_PER_MESSAGE'
    conversations_with_bots = conversations_with_bots - set(df[df['THROUGH_SKILL'].str.contains('N8N_TEST', na=False, case=False)]['CONVERSATION_ID'].unique())
    print(f"    🏢 Conversations with department bots after removing N8N_TEST through_skill: {len(conversations_with_bots)}")
    
    
    # Filter 4: Engagement filter - Conversations that meet both criteria
    engagement_valid_conversations = conversations_with_consumer.intersection(conversations_with_service)
    print(f"    ✅ Engagement-valid conversations: {len(engagement_valid_conversations)}")
    
    # Remove N8N_TEST from engagement_valid_conversations using both TARGET_SKILL_PER_MESSAGE and THROUGH_SKILL
    engagement_valid_conversations = engagement_valid_conversations - set(df[df['TARGET_SKILL_PER_MESSAGE'].str.contains('N8N_TEST', na=False, case=False)]['CONVERSATION_ID'].unique())
    engagement_valid_conversations = engagement_valid_conversations - set(df[df['THROUGH_SKILL'].str.contains('N8N_TEST', na=False, case=False)]['CONVERSATION_ID'].unique())
    print(f"    ✅ Engagement-valid conversations after removing N8N_TEST: {len(engagement_valid_conversations)}")
    
    if True:
        # Filter 5: Bot skill filter - Check THROUGH_SKILL contains any bot_skills
        conversations_with_bot_skills = set()
        for conv_id in engagement_valid_conversations:
            # Get first row of conversation
            first_row = df[df['CONVERSATION_ID'] == conv_id].iloc[0]
            through_skill = str(first_row.get('THROUGH_SKILL', ''))
            
            # Check if any bot_skill is contained in THROUGH_SKILL
            matching_bot_skills = [bot_skill for bot_skill in bot_skills if bot_skill in through_skill]
            
            # Exclude if the only matching bot skill is GPT_MAIDSAT
            if len(matching_bot_skills) > 0:
                conversations_with_bot_skills.add(conv_id)
                # if len(matching_bot_skills) == 1 and (matching_bot_skills[0] == 'GPT_MAIDSAT' or (matching_bot_skills[0] == 'Filipina_Pending_Country_of_Residence' and department_name != 'AT_Filipina')):
                #     # Skip this conversation - only GPT_MAIDSAT found
                #     continue
                # else:
                #     # Has other bot skills, include this conversation
                #     conversations_with_bot_skills.add(conv_id)
        
        print(f"    🤖 Conversations with bot skills: {len(conversations_with_bot_skills)}")
        
        # Filter the dataframe to only include conversations with bot skills
        filtered_df = df[df['CONVERSATION_ID'].isin(conversations_with_bot_skills)]
    else:
        filtered_df = df[df['CONVERSATION_ID'].isin(engagement_valid_conversations)]
    
    # Calculate filtering statistics
    filtering_stats = {
        'total_original_conversations': len(all_conversations),
        'conversations_with_consumer': len(conversations_with_consumer),
        'conversations_with_agents': len(conversations_with_agents),
        'conversations_with_bots': len(conversations_with_bots),
        'conversations_with_service': len(conversations_with_service),
        'engagement_valid_conversations': len(engagement_valid_conversations),
        'conversations_with_bot_skills': len(conversations_with_bot_skills) if apply_filter_5 else 0,
        'engagement_retention_rate': len(engagement_valid_conversations)/len(all_conversations)*100 if all_conversations else 0,
        'bot_skill_retention_rate': len(conversations_with_bot_skills)/len(engagement_valid_conversations)*100 if (apply_filter_5 and engagement_valid_conversations) else 0
    }
    
    print(f"    📈 Engagement retention: {filtering_stats['engagement_retention_rate']:.1f}%")
    print(f"    📈 Bot skill retention: {filtering_stats['bot_skill_retention_rate']:.1f}%")
    
    return filtered_df, filtering_stats


def filter_conversations_snowflake_date(df, department_name, target_date=None):
    """
    Apply date-based filtering for Snowflake data.
    Adapted from main_analytics.py date filtering logic.
    
    Date criteria:
    Remove conversations where ALL messages are from day 1 (keep conversations with at least one day 2 message)
    
    Args:
        df: DataFrame after engagement filtering
        department_name: Department name
        target_date: Target date for analysis
    
    Returns:
        Tuple: (filtered_df, filtering_stats)
    """
    print(f"  📅 Applying date filtering for {department_name}...")
    
    # Get date range information
    date_range = create_snowflake_date_range(target_date)
    day1_date = date_range['day1_date']
    day2_date = date_range['day2_date']
    
    print(f"    📅 Day 1: {day1_date}, Day 2: {day2_date}")
    
    # Convert message timestamps to dates
    df['MESSAGE_DATE'] = pd.to_datetime(df['MESSAGE_SENT_TIME']).dt.date
    
    # Get conversations before date filtering
    conversations_before_date_filter = set(df['CONVERSATION_ID'].unique())
    
    # For each conversation, check if it has at least one message from day 2
    conversations_with_day2_messages = set()
    
    for conv_id in conversations_before_date_filter:
        conv_messages = df[df['CONVERSATION_ID'] == conv_id]
        message_dates = conv_messages['MESSAGE_DATE'].unique()
        
        # Keep conversation if it has at least one message from day 2
        if day2_date in message_dates:
            conversations_with_day2_messages.add(conv_id)
    
    print(f"    📊 Conversations before date filter: {len(conversations_before_date_filter)}")
    print(f"    📊 Conversations with day 2 messages: {len(conversations_with_day2_messages)}")
    
    # Filter the dataframe to only include conversations with day 2 messages
    filtered_df = df[df['CONVERSATION_ID'].isin(conversations_with_day2_messages)]
    
    # Remove the temporary MESSAGE_DATE column
    if 'MESSAGE_DATE' in filtered_df.columns:
        filtered_df = filtered_df.drop('MESSAGE_DATE', axis=1)
    
    # Calculate filtering statistics
    filtering_stats = {
        'conversations_before_date_filter': len(conversations_before_date_filter),
        'conversations_with_day2_messages': len(conversations_with_day2_messages),
        'conversations_filtered_by_date': len(conversations_before_date_filter) - len(conversations_with_day2_messages),
        'date_retention_rate': len(conversations_with_day2_messages)/len(conversations_before_date_filter)*100 if conversations_before_date_filter else 0
    }
    
    print(f"    📈 Date retention: {filtering_stats['date_retention_rate']:.1f}%")
    
    return filtered_df, filtering_stats


def filter_conversations_snowflake_combined(df, department_name, target_date=None, apply_filter_5=True):
    """
    Apply combined filtering (engagement + date) for Snowflake data.
    Adapted from main_analytics.py filter_conversations_combined() function.
    
    Args:
        df: Preprocessed DataFrame
        department_name: Department name
        target_date: Target date for analysis
    
    Returns:
        Tuple: (filtered_df, combined_filtering_stats)
    """
    print(f"  🔄 Applying combined filtering for {department_name}...")
    
    # Get department configuration
    departments_config = get_snowflake_departments_config()
    
    # Step 1: Apply engagement filtering
    engagement_filtered_df, engagement_stats = filter_conversations_snowflake_engagement(
        df, department_name, departments_config, True
    )
    
    if engagement_filtered_df.empty:
        print(f"    ❌ No conversations passed engagement filtering")
        return pd.DataFrame(), {**engagement_stats, 'final_valid_conversations': 0}
    
    # Step 2: Apply date filtering
    final_filtered_df, date_stats = filter_conversations_snowflake_date(
        engagement_filtered_df, department_name, target_date
    )
    
    # Combine statistics
    combined_stats = {
        **engagement_stats,
        **date_stats,
        'final_valid_conversations': len(final_filtered_df['CONVERSATION_ID'].unique()) if not final_filtered_df.empty else 0
    }
    
    # Calculate overall retention rate
    if combined_stats['total_original_conversations'] > 0:
        combined_stats['overall_retention_rate'] = (
            combined_stats['final_valid_conversations'] / 
            combined_stats['total_original_conversations'] * 100
        )
    else:
        combined_stats['overall_retention_rate'] = 0
    
    print(f"    🎯 FINAL RESULT: {combined_stats['final_valid_conversations']} conversations")
    print(f"    📈 Overall retention: {combined_stats['overall_retention_rate']:.1f}%")
    
    return final_filtered_df, combined_stats


def process_department_phase1(session: snowpark.Session, department_name, target_date=None, apply_filter_5=True):
    """
    Process a single department through Phase 1 foundation layer.
    
    Steps:
    1. Load data from Snowflake table
    2. Apply preprocessing 
    3. Apply combined filtering
    4. Return filtered data and statistics
    
    Args:
        session: Snowflake session
        department_name: Department to process
        target_date: Target date for analysis
    
    Returns:
        Tuple: (filtered_df, processing_stats, success)
    """
    print(f"\n🏢 PROCESSING DEPARTMENT: {department_name}")
    print("=" * 50)
    
    try:
        # Get department configuration
        departments_config = get_snowflake_departments_config()
        
        if department_name not in departments_config:
            print(f"❌ Department '{department_name}' not configured")
            return pd.DataFrame(), {}, False
        
        dept_config = departments_config[department_name]
        table_name = dept_config['table_name']
        
        # Step 1: Load data from Snowflake table with date filtering
        print(f"📊 Step 1: Loading data from {table_name} with date filtering...")
        try:
            # Calculate the filter date (target_date + 1 day, same logic as preprocessing)
            filter_date = (datetime.strptime(target_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"    📅 Filtering for UPDATE_DATE = {filter_date}")
            
            # Build SQL query with date filtering to minimize data loading
            sql_query = f"""
            SELECT * 
            FROM {table_name} 
            WHERE DATE(UPDATED_AT) = DATE('{filter_date}')
            """
            
            print(f"    🔍 Executing SQL query with date filter...")
            raw_data_df = session.sql(sql_query).to_pandas()
            print(f"    ✅ Loaded {len(raw_data_df)} rows from Snowflake (date-filtered)")
            
        except Exception as table_error:
            table_error_details = traceback.format_exc()
            table_error_msg = f"TABLE_LOAD_ERROR: {type(table_error).__name__}: {str(table_error)}"
            print(f"    ❌ Failed to load table {table_name} with date filter: {table_error_msg}")
            print(f"    Full traceback: {table_error_details}")
            return pd.DataFrame(), {'error': table_error_msg, 'traceback': table_error_details}, False
        
        if raw_data_df.empty:
            print(f"    ⚠️  No data found in {table_name} for date {filter_date}")
            return pd.DataFrame(), {'error': f'No data found for date {filter_date}'}, False
        
        # Step 2: Apply preprocessing
        print(f"🧹 Step 2: Preprocessing data...")
        processed_df = preprocess_data_snowflake_phase1(raw_data_df, department_name, target_date)
        
        if processed_df.empty:
            print(f"    ❌ No data after preprocessing")
            return pd.DataFrame(), {'error': 'No data after preprocessing'}, False
        
        # Step 3: Apply combined filtering
        print(f"🔍 Step 3: Applying combined filtering...")
        filtered_df, filtering_stats = filter_conversations_snowflake_combined(
            processed_df, department_name, target_date, apply_filter_5
        )
        
        if filtered_df.empty:
            print(f"    ❌ No conversations passed filtering")
            return pd.DataFrame(), {**filtering_stats, 'error': 'No conversations passed filtering'}, False
        
        # Prepare final statistics
        final_stats = {
            'department': department_name,
            'table_name': table_name,
            'raw_rows': len(raw_data_df),
            'processed_rows': len(processed_df),
            'filtered_rows': len(filtered_df),
            'final_conversations': filtering_stats['final_valid_conversations'],
            **filtering_stats
        }
        
        print(f"\n✅ SUCCESS: {department_name}")
        print(f"   📊 Raw rows: {final_stats['raw_rows']:,}")
        print(f"   🧹 Processed rows: {final_stats['processed_rows']:,}")
        print(f"   🔍 Filtered rows: {final_stats['filtered_rows']:,}")
        print(f"   🎯 Final conversations: {final_stats['final_conversations']:,}")
        print(f"   📈 Overall retention: {final_stats['overall_retention_rate']:.1f}%")
        
        return filtered_df, final_stats, True
        
    except Exception as e:
        error_details = traceback.format_exc()
        error_msg = f"EXCEPTION: {type(e).__name__}: {str(e)}"
        print(f"❌ FAILED: {department_name} - {error_msg}")
        print(f"   Full traceback: {error_details}")
        return pd.DataFrame(), {'error': error_msg, 'traceback': error_details}, False


def process_department_phase1_multi_day(session: snowpark.Session, department_name, target_date=None, apply_filter_5=True):
    """
    Process a single department through Phase 1 foundation layer for multiple days.
    Fetches data for target date, target date - 1, and target date - 2, then merges them.
    
    Steps:
    1. Calculate the three dates to fetch
    2. Run process_department_phase1 for each date
    3. Merge all successful results into a single DataFrame
    4. Return combined data and comprehensive statistics
    
    Args:
        session: Snowflake session
        department_name: Department to process
        target_date: Target date for analysis (will also fetch previous 2 days)
        apply_filter_5: Whether to apply filter 5 in processing
    
    Returns:
        Tuple: (combined_df, combined_stats, success)
    """
    print(f"\n🏢📅 PROCESSING DEPARTMENT MULTI-DAY: {department_name}")
    print("=" * 60)
    
    try:
        # Calculate the three dates to fetch
        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        target_dt = datetime.strptime(target_date, '%Y-%m-%d')
        date_1 = target_dt.strftime('%Y-%m-%d')  # Target date
        date_2 = (target_dt - timedelta(days=1)).strftime('%Y-%m-%d')  # Target date - 1
        date_3 = (target_dt - timedelta(days=2)).strftime('%Y-%m-%d')  # Target date - 2
        
        dates_to_process = [date_1, date_2, date_3]
        print(f"📅 Processing dates: {date_1}, {date_2}, {date_3}")
        
        # Storage for results
        successful_dataframes = []
        all_stats = {}
        successful_dates = []
        failed_dates = []
        
        # Process each date
        for i, date in enumerate(dates_to_process, 1):
            print(f"\n📊 Processing Day {i}: {date}")
            print("-" * 40)
            
            try:
                # Run process_department_phase1 for this date
                day_df, day_stats, success = process_department_phase1(
                    session, department_name, date, apply_filter_5
                )
                
                if success and not day_df.empty:
                    # Add date identifier to the dataframe
                    day_df = day_df.copy()
                    day_df['PROCESSING_DATE'] = date
                    day_df['DAY_OFFSET'] = i - 1  # 0 for target date, 1 for -1 day, 2 for -2 days
                    
                    successful_dataframes.append(day_df)
                    all_stats[f'day_{i}_{date}'] = day_stats
                    successful_dates.append(date)
                    
                    print(f"    ✅ Day {i} ({date}): {len(day_df)} rows, {day_df['CONVERSATION_ID'].nunique()} conversations")
                else:
                    failed_dates.append(date)
                    all_stats[f'day_{i}_{date}'] = day_stats if day_stats else {'error': 'No data or processing failed'}
                    print(f"    ❌ Day {i} ({date}): Failed or no data")
                    
            except Exception as day_error:
                error_msg = f"Day {i} ({date}) processing error: {str(day_error)}"
                print(f"    ❌ {error_msg}")
                failed_dates.append(date)
                all_stats[f'day_{i}_{date}'] = {'error': error_msg}
            continue
        
        # Check if we have any successful results
        if not successful_dataframes:
            print(f"\n❌ FAILED: No data retrieved for any of the 3 days")
            combined_stats = {
                'dates_requested': dates_to_process,
                'successful_dates': successful_dates,
                'failed_dates': failed_dates,
                'total_days_processed': 0,
                'error': 'No data from any day',
                'daily_stats': all_stats
            }
            return pd.DataFrame(), combined_stats, False
        
        # Merge all successful DataFrames
        print(f"\n🔄 Merging data from {len(successful_dataframes)} successful days...")
        combined_df = pd.concat(successful_dataframes, ignore_index=True)
        
        # Calculate combined statistics
        total_rows = len(combined_df)
        total_conversations = combined_df['CONVERSATION_ID'].nunique()
        
        # Group statistics by day
        day_breakdown = {}
        for date in successful_dates:
            day_data = combined_df[combined_df['PROCESSING_DATE'] == date]
            day_breakdown[date] = {
                'rows': len(day_data),
                'conversations': day_data['CONVERSATION_ID'].nunique(),
                'percentage_of_total': (len(day_data) / total_rows * 100) if total_rows > 0 else 0
            }
        
        # Create comprehensive combined statistics
        combined_stats = {
            'dates_requested': dates_to_process,
            'successful_dates': successful_dates,
            'failed_dates': failed_dates,
            'total_days_processed': len(successful_dates),
            'combined_rows': total_rows,
            'combined_conversations': total_conversations,
            'day_breakdown': day_breakdown,
            'daily_stats': all_stats,
            'success_rate': (len(successful_dates) / len(dates_to_process) * 100)
        }
        
        # Print summary
        print(f"\n✅ MULTI-DAY SUCCESS: {department_name}")
        print(f"   📅 Days processed: {len(successful_dates)}/{len(dates_to_process)} ({combined_stats['success_rate']:.1f}%)")
        print(f"   📊 Combined rows: {total_rows:,}")
        print(f"   🎯 Combined conversations: {total_conversations:,}")
        print(f"   ✅ Successful dates: {', '.join(successful_dates)}")
        if failed_dates:
            print(f"   ❌ Failed dates: {', '.join(failed_dates)}")
        
        # Show breakdown by day
        print(f"\n📊 Day-by-day breakdown:")
        for date, stats in day_breakdown.items():
            print(f"   {date}: {stats['rows']:,} rows, {stats['conversations']:,} conversations ({stats['percentage_of_total']:.1f}%)")
        
        return combined_df, combined_stats, True
        
    except Exception as e:
        error_details = traceback.format_exc()
        error_msg = f"MULTI_DAY_EXCEPTION: {type(e).__name__}: {str(e)}"
        print(f"❌ MULTI-DAY FAILED: {department_name} - {error_msg}")
        print(f"   Full traceback: {error_details}")
        
        combined_stats = {
            'dates_requested': dates_to_process if 'dates_to_process' in locals() else [],
            'error': error_msg,
            'traceback': error_details
        }
        
        return pd.DataFrame(), combined_stats, False
