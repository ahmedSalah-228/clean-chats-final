"""
Clean Chats Core Analysis Module
Implements the core logic for analyzing clean chats using LLM_JUDGE filtering methods
"""

import sys
import os
import pandas as pd
import json
from datetime import datetime, timedelta

# Add LLM_JUDGE to path for imports
llm_judge_path = "/Users/ahmedsalah/Projects/Clean Chats/LLM_JUDGE"
if llm_judge_path not in sys.path:
    sys.path.append(llm_judge_path)

# Import LLM_JUDGE filtering logic
from clean_chats_phase2_core_analytics import process_department_phase1
from clean_chats_config import (
    get_clean_chats_departments_config,
    get_clean_chats_flagging_config,
    get_department_flagging_tables,
    get_llm_response_based_criteria,
    get_table_existence_based_criteria
)


def is_llm_response_valid(llm_response):
    """
    Check if LLM response is valid for analysis
    
    Args:
        llm_response: The LLM response string to validate
        
    Returns:
        tuple: (is_valid: bool, error_reason: str)
    """
    if not llm_response:
        return False, "EMPTY_RESPONSE"
    
    llm_response_str = str(llm_response).strip()
    
    if llm_response_str == '' or llm_response_str == 'null' or llm_response_str == 'None' or len(llm_response_str) == 0:
        return False, "EMPTY_RESPONSE"
    
    if 'error' in llm_response_str.lower():
        return False, "ERROR_IN_RESPONSE"
    
    return True, "VALID"

def process_department_phase1_from_delay_table(session, department_name, target_date):
    """
    Simplified Phase 1 processing using delay_analysis_raw_data table
    
    Args:
        session: Snowflake session
        department_name: Department to process (e.g., 'Doctors', 'MV_Resolvers')
        target_date: Target date in format 'YYYY-MM-DD'
    
    Returns:
        tuple: (filtered_df, success)
            - filtered_df: DataFrame with CONVERSATION_ID column
            - success: Boolean indicating if query succeeded and returned data
    """
    try:
        print(f"    🔍 Loading conversations from delay_analysis_raw_data for {department_name} on {target_date}")
        
        # Parse target_date to extract day and month
        from datetime import datetime
        date_obj = datetime.strptime(target_date, '%Y-%m-%d')
        day = date_obj.day
        month = date_obj.month
        year = date_obj.year

        
        
        # Query delay_analysis_raw_data table
        query = f"""
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.delay_analysis_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.sa_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}
        """

        if department_name == 'MV_Resolvers':
            query = f"""
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.delay_analysis_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.sa_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.wrong_tool_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}
        """
        if department_name=='MV_Delighters':
            query = f"""
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.delay_analysis_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            AND department = 'Delighters'        
            
            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.FALSE_PROMISES_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            AND department = 'MV_Delighters'
            """
            
        if department_name == 'CC_Resolvers':
            query = f"""
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.delay_analysis_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.sa_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.CLIENT_SUSPECTING_AI_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.MISSING_POLICY_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.WRONG_TOOL_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.MISSING_TOOL_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}
            """



        if department_name == 'CC_Sales' or department_name == 'Doctors' or department_name == 'MV_Sales':
            query = f"""
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.delay_analysis_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.sa_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.TOOL_SUMMARY
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.POLICY_VIOLATION_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}
            AND IS_PARSED = 'TRUE'

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.MISSING_POLICY_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.WRONG_ANSWER_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}
        """

        if department_name == 'AT_Filipina':
            query = f"""
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.delay_analysis_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.sa_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            AND department ILIKE 'AT_Filipina%'

            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.TOOL_SUMMARY
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            AND department ILIKE 'AT_Filipina%'


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.POLICY_VIOLATION_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            AND department ILIKE 'AT_Filipina%'
        """

        if department_name == 'AT_Filipina_In_PHL' or department_name == 'AT_Filipina_Outside_UAE' or department_name == 'AT_Filipina_Inside_UAE':
            query = f"""
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.delay_analysis_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.sa_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}

           


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.POLICY_VIOLATION_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}
        """

        if department_name == 'AT_African' or department_name == 'AT_Ethiopian' or department_name == 'Gulf_maids':
            query = f"""
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.delay_analysis_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.sa_raw_data
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.TOOL_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}


            UNION
            SELECT DISTINCT conversation_id 
            FROM LLM_EVAL.PUBLIC.POLICY_VIOLATION_RAW_DATA
            WHERE day(date) = {day:02d}
            AND month(date) = {month:02d}
            AND year(date) = {year}
            {get_department_filter_lowercase(department_name)}
            AND IS_PARSED = 'TRUE'
        """

        
        print(f"    📊 Executing query: day={day:02d}, month={month:02d}, year={year}, department={department_name}")
        
        # Execute query
        result = session.sql(query).collect()
        
        if not result:
            print(f"    ⚠️  No conversations found for {department_name} on {target_date}")
            return pd.DataFrame(), False
        
        # Convert to DataFrame
        conversation_ids = [row['CONVERSATION_ID'] for row in result]
        filtered_df = pd.DataFrame({'CONVERSATION_ID': conversation_ids})
        
        print(f"    ✅ Found {len(conversation_ids)} conversations for {department_name}")
        
        return filtered_df, True
        
    except Exception as e:
        print(f"    ❌ Error loading conversations from delay_analysis_raw_data: {str(e)}")
        return pd.DataFrame(), False


def get_department_filter(department_name):
    """
    Get the appropriate department filter for SQL queries
    
    Args:
        department_name: The department name
        
    Returns:
        str: SQL WHERE clause for department filtering
    """
    if department_name == 'AT_Filipina':
        return "AND DEPARTMENT ILIKE 'AT_Filipina%'"
    else:
        return f"AND DEPARTMENT = '{department_name}'"

def get_department_filter_lowercase(department_name):
    """
    Get the appropriate department filter for SQL queries with lowercase 'department' column
    
    Args:
        department_name: The department name
        
    Returns:
        str: SQL WHERE clause for department filtering
    """
    if department_name == 'AT_Filipina':
        return "AND department ILIKE 'AT_Filipina%'"
    else:
        return f"AND department = '{department_name}'"

def check_all_conversations_flagged_status_batch(session, conversation_ids, department_name, target_date):
    """
    Check flagging status for ALL conversations in a single batch operation (OPTIMIZED)
    
    Args:
        session: Snowflake session
        conversation_ids: List of conversation IDs to check
        department_name: Department name
        target_date: Target date for analysis
        
    Returns:
        Dictionary mapping conversation_id to flagging status
    """
    print(f"    🚀 Batch checking {len(conversation_ids)} conversations across all flagging tables...")
    
    flagging_tables = get_department_flagging_tables(department_name)
    
    # Initialize results for all conversations
    all_flagging_results = {}
    for conv_id in conversation_ids:
        all_flagging_results[conv_id] = {
            'conversation_id': conv_id,
            'is_flagged': False,
            'flagging_sources': [],
            'flagging_details': {},
            'sa_nps_flagged': False,
            'specialized_prompt_flagged': False,
            'has_assessment_errors': False,
            'assessment_error_details': {}
        }
    
    # Create conversation ID list for SQL IN clause
    conv_ids_str = "', '".join(conversation_ids)
    
    # Process each flagging table with BATCH queries
    for table_config in flagging_tables:
        table_name = table_config['table']
        prompt_type = table_config['prompt_type']
        criteria = table_config['flagging_criteria']
        
        try:
            if criteria == 'nps_score_1':
                # BATCH: Check SA_RAW_DATA for ALL conversations with NPS score = 1
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                """
                
                results = session.sql(query).collect()
                
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'nps_score_1',
                                'error_reason': error_reason,
                                'description': f'SA analysis assessment failed: {error_reason}'
                            }
                            continue
                        
                        # Parse JSON response to get NPS score
                        try:
                            response_data = json.loads(llm_response)
                            nps_score = response_data.get('NPS_score', 0)
                            if nps_score == 1:
                                result['is_flagged'] = True
                                result['sa_nps_flagged'] = True
                                result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                                result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'nps_score_1',
                                    'nps_score': nps_score,
                                    'description': 'SA analysis with NPS score = 1'
                                }
                        except (json.JSONDecodeError, KeyError):
                            # JSON parsing failed - mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'nps_score_1',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': 'SA analysis JSON parsing failed'
                            }
                            
            elif criteria == 'contains_yes':
                # BATCH: Check specialized prompt tables for ALL conversations (to detect errors)
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                """
                
                results = session.sql(query).collect()
                
                # Process each response for errors and flagging
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'contains_yes',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        
                        # Check for YES in valid response
                        if 'YES' in str(llm_response).upper():
                            if conv_id not in flagged_convs:
                                flagged_convs[conv_id] = 0
                            flagged_convs[conv_id] += 1
                
                # Update flagging results for conversations flagged with YES
                for conv_id, count in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'contains_yes',
                            'record_count': count,
                            'description': f'{prompt_type} analysis flagged with YES response'
                        }
                        
            elif criteria == 'contains_true':
                # BATCH: Check specialized prompt tables for ALL conversations (to detect errors)
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                """
                
                results = session.sql(query).collect()
                
                # Process each response for errors and flagging
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'contains_true',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        
                        # Check for TRUE in valid response
                        if 'TRUE' in str(llm_response).upper():
                            if conv_id not in flagged_convs:
                                flagged_convs[conv_id] = 0
                            flagged_convs[conv_id] += 1
                
                # Update flagging results for conversations flagged with TRUE
                for conv_id, count in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'contains_true',
                            'record_count': count,
                            'description': f'{prompt_type} analysis flagged with TRUE response'
                        }
                        
            elif criteria == 'contains_rogue_answer':
                # BATCH: Check specialized prompt tables for ALL conversations (to detect errors)
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                """
                
                results = session.sql(query).collect()
                
                # Process each response for errors and flagging
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'contains_rogue_answer',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        
                        # Check for ROGUEANSWER in valid response
                        if 'ROGUEANSWER' in str(llm_response).upper():
                            if conv_id not in flagged_convs:
                                flagged_convs[conv_id] = 0
                            flagged_convs[conv_id] += 1
                
                # Update flagging results for conversations flagged with ROGUEANSWER
                for conv_id, count in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'contains_rogue_answer',
                            'record_count': count,
                            'description': f'{prompt_type} analysis flagged with RogueAnswer response'
                        }
                        
            elif criteria == 'exists_only':
                # BATCH: Check if conversation ID exists in table (regardless of response content)
                query = f"""
                SELECT 
                    CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                """
                if table_name == 'CHATCC_REPORTED_ISSUES':
                    query = f"""
                SELECT 
                    CONVERSATION_ID
                FROM LLM_EVAL.RAW_DATA.{table_name}
                WHERE CONVERSATION_ID IN ('{conv_ids_str}')
                """
                
                results = session.sql(query).collect()
                
                # Group results by conversation ID
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id not in flagged_convs:
                        flagged_convs[conv_id] = 0
                    flagged_convs[conv_id] += 1
                
                # Update flagging results for affected conversations
                for conv_id, count in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'exists_only',
                            'record_count': count,
                            'description': f'{prompt_type} analysis flagged by existence in table (issue detected)'
                        }
                        
            elif criteria == 'clarification_count':
                # BATCH: Check clarity_score_raw_data for ClarificationMessages count > 0
                print(f"    🔍 Checking clarity_score_raw_data for ClarificationMessages count > 0")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")

                
                # Parse JSON responses and check clarification counts
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'clarification_count',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check for ClarificationMessages (primary key)
                            clarification_count = response_data.get('ClarificationMessagesTotal')
                            # If not found, check for ClarificationMessagesTotal (fallback key)
                            if clarification_count is None:
                                clarification_count = response_data.get('ClarificationMessages')
                            # Convert to int and check if > 0
                            if clarification_count is not None:
                                try:
                                    clarification_count = int(clarification_count)
                                    if clarification_count > 0:
                                        if conv_id not in flagged_convs:
                                            flagged_convs[conv_id] = {'count': 0, 'clarification_count': clarification_count}
                                        flagged_convs[conv_id]['count'] += 1
                                        
                                except (ValueError, TypeError):
                                    # Mark as assessment error if clarification_count is not a valid number
                                    result['has_assessment_errors'] = True
                                    result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                        'criteria': 'clarification_count',
                                        'error_reason': 'INVALID_NUMBER_FORMAT',
                                        'description': f'{prompt_type} analysis - clarification count not a valid number'
                                    }
                                    continue
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'clarification_count',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse clarification data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'clarification_count',
                            'record_count': data['count'],
                            'clarification_count': data['clarification_count'],
                            'description': f'{prompt_type} analysis flagged with {data["clarification_count"]} clarification messages'
                        }

            elif criteria == 'confusing_policy_yes':
                # BATCH: Check UNCLEAR_POLICY_RAW_DATA for confusingPolicy = "Yes"
                print(f"    🔍 Checking UNCLEAR_POLICY_RAW_DATA for confusingPolicy = 'Yes'")
                
                
                
                # STEP 2: Continue with normal confusing_policy_yes logic for remaining conversations
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check confusingPolicy
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'confusing_policy_yes',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check for confusingPolicy (case insensitive)
                            confusing_policy = response_data.get('confusingPolicy')
                            
                            # Check if confusingPolicy is "Yes" (case insensitive)
                            if confusing_policy is not None:
                                if str(confusing_policy).upper() == 'YES':
                                    if conv_id not in flagged_convs:
                                        flagged_convs[conv_id] = {'count': 0, 'confusing_policy_value': confusing_policy}
                                    flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'confusing_policy_yes',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse unclear policy data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'confusing_policy_yes',
                            'record_count': data['count'],
                            'confusing_policy_value': data['confusing_policy_value'],
                            'description': f'{prompt_type} analysis flagged - confusing policy detected (confusingPolicy = {data["confusing_policy_value"]})'
                        }

            elif criteria == 'missing_policy_yes':
                # BATCH: Check MISSING_POLICY_RAW_DATA for missingPolicy = "Yes"
                print(f"    🔍 Checking MISSING_POLICY_RAW_DATA for missingPolicy = 'Yes'")
                
                # Continue with normal missing_policy_yes logic
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check missingPolicy
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'missing_policy_yes',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check for missingPolicy (case insensitive)
                            missing_policy = response_data.get('missingPolicy')
                            
                            # Check if missingPolicy is "Yes" (case insensitive)
                            if missing_policy is not None:
                                if str(missing_policy).upper() == 'YES':
                                    if conv_id not in flagged_convs:
                                        flagged_convs[conv_id] = {'count': 0, 'missing_policy_value': missing_policy}
                                    flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'missing_policy_yes',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse missing policy data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missing_policy_yes',
                            'record_count': data['count'],
                            'missing_policy_value': data['missing_policy_value'],
                            'description': f'{prompt_type} analysis flagged - missing policy detected (missingPolicy = {data["missing_policy_value"]})'
                        }

            elif criteria == 'cc_sales_unclear_policy_true':
                # BATCH: Check POLICY_VIOLATION_RAW_DATA for unclear_policy = true (CC_Sales)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for unclear_policy = true (CC_Sales)")
                
                # STEP 1: First check POLICY_VIOLATION_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)")
                is_parsed_query = f"""
                SELECT DISTINCT CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.POLICY_VIOLATION_RAW_DATA
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'FALSE'
                """
                
                is_parsed_results = session.sql(is_parsed_query).collect()
                print(f"    🔍 Found {len(is_parsed_results)} conversations with IS_PARSED = 'FALSE'")
                
                # Mark conversations with IS_PARSED='FALSE' as assessment errors
                for row in is_parsed_results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['has_assessment_errors'] = True
                        result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'cc_sales_unclear_policy_true',
                            'error_reason': 'IS_PARSED_FALSE',
                            'description': f'{prompt_type} analysis parsing failed: IS_PARSED flag set to FALSE'
                        }
                
                # STEP 2: Continue with normal cc_sales_unclear_policy_true logic
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check unclear_policy
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'cc_sales_unclear_policy_true',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check for unclear_policy (case insensitive boolean)
                            unclear_policy = response_data.get('unclear_policy')
                            
                            # Check if unclear_policy is true (case insensitive)
                            if unclear_policy is not None:
                                if str(unclear_policy).upper() == 'TRUE':
                                    if conv_id not in flagged_convs:
                                        flagged_convs[conv_id] = {'count': 0, 'unclear_policy_value': unclear_policy}
                                    flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'cc_sales_unclear_policy_true',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse CC_Sales unclear policy data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'cc_sales_unclear_policy_true',
                            'record_count': data['count'],
                            'unclear_policy_value': data['unclear_policy_value'],
                            'description': f'{prompt_type} analysis flagged - CC_Sales unclear policy detected (unclear_policy = {data["unclear_policy_value"]})'
                        }

            elif criteria == 'cc_sales_missing_policy_true':
                # BATCH: Check POLICY_VIOLATION_RAW_DATA for missing_policy = true (CC_Sales)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for missing_policy = true (CC_Sales)")
                
                # STEP 1: First check POLICY_VIOLATION_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)")
                is_parsed_query = f"""
                SELECT DISTINCT CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.POLICY_VIOLATION_RAW_DATA
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'FALSE'
                """
                
                is_parsed_results = session.sql(is_parsed_query).collect()
                print(f"    🔍 Found {len(is_parsed_results)} conversations with IS_PARSED = 'FALSE'")
                
                # Mark conversations with IS_PARSED='FALSE' as assessment errors
                for row in is_parsed_results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['has_assessment_errors'] = True
                        result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'cc_sales_missing_policy_true',
                            'error_reason': 'IS_PARSED_FALSE',
                            'description': f'{prompt_type} analysis parsing failed: IS_PARSED flag set to FALSE'
                        }
                
                # STEP 2: Continue with normal cc_sales_missing_policy_true logic
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check missing_policy
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'cc_sales_missing_policy_true',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check for missing_policy (case insensitive boolean)
                            missing_policy = response_data.get('missing_policy')
                            
                            # Check if missing_policy is true (case insensitive)
                            if missing_policy is not None:
                                if str(missing_policy).upper() == 'TRUE':
                                    if conv_id not in flagged_convs:
                                        flagged_convs[conv_id] = {'count': 0, 'missing_policy_value': missing_policy}
                                    flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'cc_sales_missing_policy_true',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse CC_Sales missing policy data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'cc_sales_missing_policy_true',
                            'record_count': data['count'],
                            'missing_policy_value': data['missing_policy_value'],
                            'description': f'{prompt_type} analysis flagged - CC_Sales missing policy detected (missing_policy = {data["missing_policy_value"]})'
                        }

            elif criteria == 'avoid_visit':
                # BATCH: Check DOCTORS_UNNECESSARY_CLINIC_RAW_DATA for could_avoid_visit = true
                print(f"    🔍 Checking DOCTORS_UNNECESSARY_CLINIC_RAW_DATA for could_avoid_visit = true")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check could_avoid_visit
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'avoid_visit',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check for could_avoid_visit
                            could_avoid_visit = response_data.get('could_avoid_visit')
                            
                            # Check if could_avoid_visit is true (boolean or string 'true')
                            if could_avoid_visit is not None:
                                if (isinstance(could_avoid_visit, bool) and could_avoid_visit) or \
                                   (isinstance(could_avoid_visit, str) and could_avoid_visit.lower() == 'true'):
                                    if conv_id not in flagged_convs:
                                        flagged_convs[conv_id] = {'count': 0, 'avoid_visit_value': could_avoid_visit}
                                    flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'avoid_visit',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse avoid_visit data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'avoid_visit',
                            'record_count': data['count'],
                            'avoid_visit_value': data['avoid_visit_value'],
                            'description': f'{prompt_type} analysis flagged - clinic visit could be avoided'
                        }

            elif criteria == 'wrong_answer_violation':
                # BATCH: Check POLICY_VIOLATION_RAW_DATA for "Wrong Answer" in violations array (AT_Filipina)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for Wrong Answer violation_type (AT_Filipina)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check violations array for "Wrong Answer"
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'wrong_answer_violation',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Handle case where response_data might be a list instead of dict
                            if isinstance(response_data, list):
                                # Mark as assessment error - unexpected format
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'wrong_answer_violation',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with violations array'
                                }
                                continue
                            
                            # Check for violations array
                            violations = response_data.get('violations', [])
                            
                            # Ensure violations is a list
                            if not isinstance(violations, list):
                                # Mark as assessment error - violations is not a list
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'wrong_answer_violation',
                                    'error_reason': 'INVALID_VIOLATIONS_FORMAT',
                                    'description': f'{prompt_type} analysis - violations field is not a list'
                                }
                                continue
                            
                            # Look for "Wrong Answer" violation_type in any violation
                            wrong_answer_found = False
                            wrong_answer_count = 0
                            for violation in violations:
                                if not isinstance(violation, dict):
                                    # Skip invalid violation entries but don't fail the whole assessment
                                    continue
                                violation_type = violation.get('violation_type', '')
                                if violation_type.upper() == 'WRONG ANSWER':
                                    wrong_answer_found = True
                                    wrong_answer_count += 1
                            
                            if wrong_answer_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'wrong_answer_violations': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['wrong_answer_violations'] = wrong_answer_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'wrong_answer_violation',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse wrong answer violation data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'wrong_answer_violation',
                            'record_count': data['count'],
                            'wrong_answer_violations': data['wrong_answer_violations'],
                            'description': f'{prompt_type} analysis flagged - {data["wrong_answer_violations"]} Wrong Answer violation(s) detected'
                        }

            elif criteria == 'unclear_policy_violation':
                # BATCH: Check POLICY_VIOLATION_RAW_DATA for "Unclear Policy" in violations array (AT_Filipina)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for Unclear Policy violation_type (AT_Filipina)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check violations array for "Unclear Policy"
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'unclear_policy_violation',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            print(f"    ⚠️  Failed to parse unclear policy violation data for this conversation: {conv_id}")
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Handle case where response_data might be a list instead of dict
                            if isinstance(response_data, list):
                                # Mark as assessment error - unexpected format
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'unclear_policy_violation',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with violations array'
                                }
                                continue
                            
                            # Check for violations array
                            violations = response_data.get('violations', [])
                            
                            # Ensure violations is a list
                            if not isinstance(violations, list):
                                # Mark as assessment error - violations is not a list
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'unclear_policy_violation',
                                    'error_reason': 'INVALID_VIOLATIONS_FORMAT',
                                    'description': f'{prompt_type} analysis - violations field is not a list'
                                }
                                continue
                            
                            # Look for "Unclear Policy" violation_type in any violation
                            unclear_policy_found = False
                            unclear_policy_count = 0
                            for violation in violations:
                                if not isinstance(violation, dict):
                                    # Skip invalid violation entries but don't fail the whole assessment
                                    continue
                                violation_type = violation.get('violation_type', '')
                                if violation_type.upper() == 'UNCLEAR POLICY':
                                    unclear_policy_found = True
                                    unclear_policy_count += 1
                            
                            if unclear_policy_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'unclear_policy_violations': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['unclear_policy_violations'] = unclear_policy_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'unclear_policy_violation',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse unclear policy violation data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'unclear_policy_violation',
                            'record_count': data['count'],
                            'unclear_policy_violations': data['unclear_policy_violations'],
                            'description': f'{prompt_type} analysis flagged - {data["unclear_policy_violations"]} Unclear Policy violation(s) detected'
                        }

            elif criteria == 'missing_policy_violation':
                # BATCH: Check POLICY_VIOLATION_RAW_DATA for "missing policy" in violations array (AT_Filipina)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for Missing Policy violation_type (AT_Filipina)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check violations array for "missing policy"
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'missing_policy_violation',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]  # Remove '```json'
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]   # Remove '```'
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]  # Remove trailing '```'
                            
                            # Final strip to remove any whitespace
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Handle case where response_data might be a list instead of dict
                            if isinstance(response_data, list):
                                # Mark as assessment error - unexpected format
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'missing_policy_violation',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with violations array'
                                }
                                continue
                            
                            # Check for violations array
                            violations = response_data.get('violations', [])
                            
                            # Ensure violations is a list
                            if not isinstance(violations, list):
                                # Mark as assessment error - violations is not a list
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'missing_policy_violation',
                                    'error_reason': 'INVALID_VIOLATIONS_FORMAT',
                                    'description': f'{prompt_type} analysis - violations field is not a list'
                                }
                                continue
                            
                            # Look for "missing policy" violation_type in any violation (case insensitive)
                            missing_policy_found = False
                            missing_policy_count = 0
                            for violation in violations:
                                if not isinstance(violation, dict):
                                    # Skip invalid violation entries but don't fail the whole assessment
                                    continue
                                violation_type = violation.get('violation_type', '')
                                if violation_type.upper() == 'MISSING POLICY':
                                    missing_policy_found = True
                                    missing_policy_count += 1
                            
                            if missing_policy_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'missing_policy_violations': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['missing_policy_violations'] = missing_policy_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'missing_policy_violation',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse missing policy violation data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missing_policy_violation',
                            'record_count': data['count'],
                            'missing_policy_violations': data['missing_policy_violations'],
                            'description': f'{prompt_type} analysis flagged - {data["missing_policy_violations"]} Missing Policy violation(s) detected'
                        }

            elif criteria == 'wrong_tool_issue_type':
                # BATCH: Check TOOL_RAW_DATA for "WRONG_TOOL_CALLED" in ANALYSIS_REPORT (AT_African, AT_Ethiopian)
                print(f"    🔍 Checking TOOL_RAW_DATA for WRONG_TOOL_CALLED in ANALYSIS_REPORT (AT_African/AT_Ethiopian)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check ANALYSIS_REPORT for WRONG_TOOL_CALLED
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'wrong_tool_issue_type',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            
                            # Final strip
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Handle case where response_data might be a list instead of dict
                            if isinstance(response_data, list):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'wrong_tool_issue_type',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with ANALYSIS_REPORT'
                                }
                                continue
                            
                            # Navigate to ANALYSIS_REPORT.TOOL_COMPLIANCE_ANALYSIS
                            analysis_report = response_data.get('ANALYSIS_REPORT', {})
                            if not isinstance(analysis_report, dict):
                                continue
                            
                            tool_compliance = analysis_report.get('TOOL_COMPLIANCE_ANALYSIS', [])
                            if not isinstance(tool_compliance, list):
                                continue
                            
                            # Look for WRONG_TOOL_CALLED in ISSUE_TYPE
                            wrong_tool_found = False
                            wrong_tool_count = 0
                            for issue in tool_compliance:
                                if not isinstance(issue, dict):
                                    continue
                                issue_type = issue.get('ISSUE_TYPE', '')
                                if issue_type == 'WRONG_TOOL_CALLED':
                                    wrong_tool_found = True
                                    wrong_tool_count += 1
                            
                            if wrong_tool_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'wrong_tool_issues': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['wrong_tool_issues'] = wrong_tool_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'wrong_tool_issue_type',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse wrong tool issue data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'wrong_tool_issue_type',
                            'record_count': data['count'],
                            'wrong_tool_issues': data['wrong_tool_issues'],
                            'description': f'{prompt_type} analysis flagged - {data["wrong_tool_issues"]} WRONG_TOOL_CALLED issue(s) detected'
                        }

            elif criteria == 'missed_tool_issue_type':
                # BATCH: Check TOOL_RAW_DATA for "MISSED_TO_BE_CALLED" in ANALYSIS_REPORT (AT_African, AT_Ethiopian)
                print(f"    🔍 Checking TOOL_RAW_DATA for MISSED_TO_BE_CALLED in ANALYSIS_REPORT (AT_African/AT_Ethiopian)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check ANALYSIS_REPORT for MISSED_TO_BE_CALLED
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'missed_tool_issue_type',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            
                            # Final strip
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Handle case where response_data might be a list instead of dict
                            if isinstance(response_data, list):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'missed_tool_issue_type',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with ANALYSIS_REPORT'
                                }
                                continue
                            
                            # Navigate to ANALYSIS_REPORT.TOOL_COMPLIANCE_ANALYSIS
                            analysis_report = response_data.get('ANALYSIS_REPORT', {})
                            if not isinstance(analysis_report, dict):
                                continue
                            
                            tool_compliance = analysis_report.get('TOOL_COMPLIANCE_ANALYSIS', [])
                            if not isinstance(tool_compliance, list):
                                continue
                            
                            # Look for MISSED_TO_BE_CALLED in ISSUE_TYPE
                            missed_tool_found = False
                            missed_tool_count = 0
                            for issue in tool_compliance:
                                if not isinstance(issue, dict):
                                    continue
                                issue_type = issue.get('ISSUE_TYPE', '')
                                if issue_type == 'MISSED_TO_BE_CALLED':
                                    missed_tool_found = True
                                    missed_tool_count += 1
                            
                            if missed_tool_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'missed_tool_issues': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['missed_tool_issues'] = missed_tool_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'missed_tool_issue_type',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse missed tool issue data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missed_tool_issue_type',
                            'record_count': data['count'],
                            'missed_tool_issues': data['missed_tool_issues'],
                            'description': f'{prompt_type} analysis flagged - {data["missed_tool_issues"]} MISSED_TO_BE_CALLED issue(s) detected'
                        }

            elif criteria == 'unclear_policy_issue_type':
                # BATCH: Check POLICY_VIOLATION_RAW_DATA for "UNCLEAR_POLICY_AMBIGUITY" in ANALYSIS_REPORT (AT_African, AT_Ethiopian)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for UNCLEAR_POLICY_AMBIGUITY in ANALYSIS_REPORT (AT_African/AT_Ethiopian)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check ANALYSIS_REPORT for UNCLEAR_POLICY_AMBIGUITY
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'unclear_policy_issue_type',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            
                            # Final strip
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Handle case where response_data might be a list instead of dict
                            if isinstance(response_data, list):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'unclear_policy_issue_type',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with ANALYSIS_REPORT'
                                }
                                continue
                            
                            # Navigate to ANALYSIS_REPORT.POLICY_COMPLIANCE_ISSUES
                            analysis_report = response_data.get('ANALYSIS_REPORT', {})
                            if not isinstance(analysis_report, dict):
                                continue
                            
                            policy_compliance = analysis_report.get('POLICY_COMPLIANCE_ISSUES', [])
                            if not isinstance(policy_compliance, list):
                                continue
                            
                            # Look for UNCLEAR_POLICY_AMBIGUITY in ISSUE_TYPE
                            unclear_policy_found = False
                            unclear_policy_count = 0
                            for issue in policy_compliance:
                                if not isinstance(issue, dict):
                                    continue
                                issue_type = issue.get('ISSUE_TYPE', '')
                                if issue_type == 'UNCLEAR_POLICY_AMBIGUITY':
                                    unclear_policy_found = True
                                    unclear_policy_count += 1
                            
                            if unclear_policy_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'unclear_policy_issues': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['unclear_policy_issues'] = unclear_policy_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'unclear_policy_issue_type',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse unclear policy issue data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'unclear_policy_issue_type',
                            'record_count': data['count'],
                            'unclear_policy_issues': data['unclear_policy_issues'],
                            'description': f'{prompt_type} analysis flagged - {data["unclear_policy_issues"]} UNCLEAR_POLICY_AMBIGUITY issue(s) detected'
                        }

            elif criteria == 'missing_policy_issue_type':
                # BATCH: Check POLICY_VIOLATION_RAW_DATA for "MISSING_POLICY_ADHERENCE" in ANALYSIS_REPORT (AT_African, AT_Ethiopian)
                print(f"    🔍 Checking POLICY_VIOLATION_RAW_DATA for MISSING_POLICY_ADHERENCE in ANALYSIS_REPORT (AT_African/AT_Ethiopian)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check ANALYSIS_REPORT for MISSING_POLICY_ADHERENCE
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'missing_policy_issue_type',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            
                            # Final strip
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Handle case where response_data might be a list instead of dict
                            if isinstance(response_data, list):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'missing_policy_issue_type',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with ANALYSIS_REPORT'
                                }
                                continue
                            
                            # Navigate to ANALYSIS_REPORT.POLICY_COMPLIANCE_ISSUES
                            analysis_report = response_data.get('ANALYSIS_REPORT', {})
                            if not isinstance(analysis_report, dict):
                                continue
                            
                            policy_compliance = analysis_report.get('POLICY_COMPLIANCE_ISSUES', [])
                            if not isinstance(policy_compliance, list):
                                continue
                            
                            # Look for MISSING_POLICY_ADHERENCE in ISSUE_TYPE
                            missing_policy_found = False
                            missing_policy_count = 0
                            for issue in policy_compliance:
                                if not isinstance(issue, dict):
                                    continue
                                issue_type = issue.get('ISSUE_TYPE', '')
                                if issue_type == 'MISSING_POLICY_ADHERENCE':
                                    missing_policy_found = True
                                    missing_policy_count += 1
                            
                            if missing_policy_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'missing_policy_issues': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['missing_policy_issues'] = missing_policy_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'missing_policy_issue_type',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse missing policy issue data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missing_policy_issue_type',
                            'record_count': data['count'],
                            'missing_policy_issues': data['missing_policy_issues'],
                            'description': f'{prompt_type} analysis flagged - {data["missing_policy_issues"]} MISSING_POLICY_ADHERENCE issue(s) detected'
                        }

            elif criteria == 'doctors_missing_policy_detected':
                # BATCH: Check MISSING_POLICY_RAW_DATA for missing_policy_detected = true (Doctors)
                print(f"    🔍 Checking MISSING_POLICY_RAW_DATA for missing_policy_detected = true (Doctors)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check for missing_policy_detected = true
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'doctors_missing_policy_detected',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            
                            # Final strip
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Handle case where response_data might be a list instead of dict
                            if isinstance(response_data, list):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'doctors_missing_policy_detected',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with missing_policy_detected field'
                                }
                                continue
                            
                            # Check for missing_policy_detected = true
                            missing_policy_detected = response_data.get('missing_policy_detected', False)
                            
                            if missing_policy_detected is True or (isinstance(missing_policy_detected, str) and missing_policy_detected.lower() == 'true'):
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0}
                                flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'doctors_missing_policy_detected',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse missing policy detected data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'doctors_missing_policy_detected',
                            'record_count': data['count'],
                            'description': f'{prompt_type} analysis flagged - missing_policy_detected = true'
                        }

            elif criteria == 'cc_resolvers_properly_called_no':
                # BATCH: Check WRONG_TOOL_RAW_DATA for properlyCalled = "No" in array (CC_Resolvers)
                print(f"    🔍 Checking WRONG_TOOL_RAW_DATA for properlyCalled = 'No' in array (CC_Resolvers)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check for properlyCalled = "No" in array
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'cc_resolvers_properly_called_no',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            
                            # Final strip
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response - can be array or dict with various wrapper key names
                            response_data = json.loads(cleaned_response)
                            
                            # Handle both formats:
                            # Format 1: Direct array: [{...}, {...}]
                            # Format 2: Wrapped dict: {"toolCalled": [{...}, {...}]} (with variations)
                            # Format 3: Empty dict: {} (means clean - no wrong tools)
                            # Format 4: Single tool object: {"toolName": "...", "properlyCalled": "...", ...}
                            tools_array = None
                            if isinstance(response_data, list):
                                # Direct array format
                                tools_array = response_data
                            elif isinstance(response_data, dict):
                                # Check if empty dict - this means clean (no wrong tools called)
                                if len(response_data) == 0:
                                    # Empty dict {} - explicitly clean, don't flag
                                    continue
                                
                                # Check if this is a single tool object (has toolName and properlyCalled)
                                if 'toolName' in response_data and 'properlyCalled' in response_data:
                                    # Single tool object - treat as array with one element
                                    tools_array = [response_data]
                                else:
                                    # Try to find the array in the dict - check common key variations
                                    # Common variations due to LLM inconsistencies:
                                    possible_keys = [
                                        'toolCalled', 'toolsCalled', 'toolName', 'tool_called', 
                                        'ToolCalled', 'ToolsCalled', 'Tools', 'Tool_Called',
                                        'toolcalled', 'toolscalled', 'TOOLCALLED', 'TOOLS',
                                        'tool', 'Tool', 'TOOL', 'toolCall', 'toolCalls',
                                        'ToolCall', 'ToolCalls', 'tool_calls', 'tool_call','toolCalls', 'toolCalled', 'toolEvaluations', 'toolCallsEvaluation', 
                                          'toolsCalled', 'results', 'tools'
                                    ]
                                    
                                    found_key = None
                                    for key in possible_keys:
                                        if key in response_data:
                                            found_key = key
                                            break
                                    
                                    if found_key:
                                        # Found a matching key - extract the array
                                        tools_array = response_data.get(found_key, [])
                                        if not isinstance(tools_array, list):
                                            result['has_assessment_errors'] = True
                                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                                'criteria': 'cc_resolvers_properly_called_no',
                                                'error_reason': 'INVALID_TOOLS_ARRAY_FORMAT',
                                                'description': f'{prompt_type} analysis - "{found_key}" value is not an array'
                                            }
                                            continue
                                    else:
                                        # No matching key found - try to find any array value
                                        # If dict has only 1 key and it's an array, use it
                                        if len(response_data) == 1:
                                            only_key = list(response_data.keys())[0]
                                            only_value = response_data[only_key]
                                            if isinstance(only_value, list):
                                                tools_array = only_value
                                                print(f"    ℹ️  Using array from unknown key '{only_key}' for conv {conv_id}")
                                            else:
                                                # Single key but not an array
                                                result['has_assessment_errors'] = True
                                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                                    'criteria': 'cc_resolvers_properly_called_no',
                                                    'error_reason': 'UNEXPECTED_DICT_FORMAT',
                                                    'description': f'{prompt_type} analysis - Dict has key "{only_key}" but value is not an array'
                                                }
                                                continue
                                        else:
                                            # Multiple keys, none matching - unexpected format
                                            result['has_assessment_errors'] = True
                                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                                'criteria': 'cc_resolvers_properly_called_no',
                                                'error_reason': 'UNEXPECTED_DICT_FORMAT',
                                                'description': f'{prompt_type} analysis - Dict without recognized tool array key. Keys found: {list(response_data.keys())}'
                                            }
                                            continue
                            else:
                                # Neither list nor dict
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'cc_resolvers_properly_called_no',
                                    'error_reason': 'INVALID_JSON_TYPE',
                                    'description': f'{prompt_type} analysis - JSON response is neither array nor object'
                                }
                                continue
                            
                            # Check each tool object in the array for properlyCalled = "No"
                            properly_called_no_found = False
                            properly_called_no_count = 0
                            for tool_obj in tools_array:
                                if not isinstance(tool_obj, dict):
                                    continue
                                properly_called = tool_obj.get('properlyCalled', '')
                                if properly_called == "No":
                                    properly_called_no_found = True
                                    properly_called_no_count += 1
                            
                            if properly_called_no_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'properly_called_no_count': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['properly_called_no_count'] = properly_called_no_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'cc_resolvers_properly_called_no',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse properly called data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'cc_resolvers_properly_called_no',
                            'record_count': data['count'],
                            'properly_called_no_count': data['properly_called_no_count'],
                            'description': f'{prompt_type} analysis flagged - {data["properly_called_no_count"]} tool(s) with properlyCalled = "No"'
                        }

            elif criteria == 'cc_resolvers_missed_call_yes':
                # BATCH: Check MISSING_TOOL_RAW_DATA for missedCall = "Yes" in tool objects (CC_Resolvers)
                print(f"    🔍 Checking MISSING_TOOL_RAW_DATA for missedCall = 'Yes' in tool objects (CC_Resolvers)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check for missedCall = "Yes" in tool objects dict
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'cc_resolvers_missed_call_yes',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            
                            # Final strip
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response - should be a dict
                            response_data = json.loads(cleaned_response)
                            
                            # Check if response is a dict (expected format)
                            if not isinstance(response_data, dict):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'cc_resolvers_missed_call_yes',
                                    'error_reason': 'UNEXPECTED_LIST_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is a list, expected dict with tool objects'
                                }
                                continue
                            
                            # Iterate through tool objects (Tool #1, Tool #2, etc.) and check missedCall
                            missed_call_yes_found = False
                            missed_call_yes_count = 0
                            for tool_key, tool_obj in response_data.items():
                                # Skip if not a dict (defensive)
                                if not isinstance(tool_obj, dict):
                                    continue
                                missed_call = tool_obj.get('missedCall', '')
                                if missed_call == "Yes":
                                    missed_call_yes_found = True
                                    missed_call_yes_count += 1
                            
                            if missed_call_yes_found:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'missed_call_yes_count': 0}
                                flagged_convs[conv_id]['count'] += 1
                                flagged_convs[conv_id]['missed_call_yes_count'] = missed_call_yes_count
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'cc_resolvers_missed_call_yes',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse missed call data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'cc_resolvers_missed_call_yes',
                            'record_count': data['count'],
                            'missed_call_yes_count': data['missed_call_yes_count'],
                            'description': f'{prompt_type} analysis flagged - {data["missed_call_yes_count"]} tool(s) with missedCall = "Yes"'
                        }

            elif criteria == 'sales_wrong_answer_true':
                # BATCH: Check WRONG_ANSWER_RAW_DATA for wrong_answer = true (CC_Sales, MV_Sales)
                print(f"    🔍 Checking WRONG_ANSWER_RAW_DATA for wrong_answer = true")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'true'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check for wrong_answer = true
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'sales_wrong_answer_true',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response - remove markdown code blocks if present
                            cleaned_response = llm_response.strip()
                            
                            # Remove ```json at the beginning
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            
                            # Remove ``` at the end
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            
                            # Final strip
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check if response is a dict (expected format)
                            if not isinstance(response_data, dict):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'sales_wrong_answer_true',
                                    'error_reason': 'UNEXPECTED_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is not a dict'
                                }
                                continue
                            
                            # Check if wrong_answer field exists and is true (case insensitive)
                            wrong_answer = response_data.get('wrong_answer', False)
                            
                            # Handle various representations of true
                            is_wrong_answer = False
                            if isinstance(wrong_answer, bool):
                                is_wrong_answer = wrong_answer
                            elif isinstance(wrong_answer, str):
                                is_wrong_answer = wrong_answer.lower() == 'true'
                            
                            # Also get the count if available
                            wrong_answer_count = response_data.get('wrong_answer_count', 0)
                            
                            if is_wrong_answer:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'wrong_answer_count': wrong_answer_count}
                                flagged_convs[conv_id]['count'] += 1
                                if wrong_answer_count > 0:
                                    flagged_convs[conv_id]['wrong_answer_count'] = wrong_answer_count
                                    
                        except (json.JSONDecodeError, KeyError) as e:
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'sales_wrong_answer_true',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse wrong answer data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'sales_wrong_answer_true',
                            'record_count': data['count'],
                            'wrong_answer_count': data['wrong_answer_count'],
                            'description': f'{prompt_type} analysis flagged - wrong_answer = true (count: {data["wrong_answer_count"]})'
                        }

            elif criteria == 'gulf_maids_missing_tool':
                # BATCH: Check TOOL_RAW_DATA for Missing Tools != "None" (Gulf_maids)
                print(f"    🔍 Checking TOOL_RAW_DATA for Missing Tools != 'None' (Gulf_maids)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check for Missing Tools
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'gulf_maids_missing_tool',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response
                            cleaned_response = llm_response.strip()
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check if response is a dict
                            if not isinstance(response_data, dict):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'gulf_maids_missing_tool',
                                    'error_reason': 'UNEXPECTED_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is not a dict'
                                }
                                continue
                            
                            # Check Missing Tools array
                            missing_tools = response_data.get('Missing Tools', [])
                            if not isinstance(missing_tools, list):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'gulf_maids_missing_tool',
                                    'error_reason': 'INVALID_MISSING_TOOLS_FORMAT',
                                    'description': f'{prompt_type} analysis - Missing Tools is not an array'
                                }
                                continue
                            
                            # Check if any tool in Missing Tools has Tool Name != "None" (case insensitive)
                            has_missing_tool = False
                            missing_tool_count = 0
                            for tool in missing_tools:
                                if isinstance(tool, dict):
                                    tool_name = tool.get('Tool Name', '').strip()
                                    if tool_name.lower() != 'none':
                                        has_missing_tool = True
                                        missing_tool_count += 1
                            
                            if has_missing_tool:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'missing_tool_count': missing_tool_count}
                                flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError) as e:
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'gulf_maids_missing_tool',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse Gulf_maids missing tool data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'gulf_maids_missing_tool',
                            'record_count': data['count'],
                            'missing_tool_count': data['missing_tool_count'],
                            'description': f'{prompt_type} analysis flagged - {data["missing_tool_count"]} missing tool(s) detected'
                        }

            elif criteria == 'gulf_maids_wrong_tool':
                # BATCH: Check TOOL_RAW_DATA for Wrong Calls > 0 in Tool Calls Summary (Gulf_maids)
                print(f"    🔍 Checking TOOL_RAW_DATA for Wrong Calls > 0 in Tool Calls Summary (Gulf_maids)")
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'TRUE'
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results")
                
                # Parse JSON responses and check for Wrong Calls
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        
                        # Check if LLM response is valid
                        is_valid, error_reason = is_llm_response_valid(llm_response)
                        
                        if not is_valid:
                            # Mark as assessment error
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'gulf_maids_wrong_tool',
                                'error_reason': error_reason,
                                'description': f'{prompt_type} analysis assessment failed: {error_reason}'
                            }
                            continue
                        try:
                            # Clean JSON response
                            cleaned_response = llm_response.strip()
                            if cleaned_response.startswith('```json'):
                                cleaned_response = cleaned_response[7:]
                            elif cleaned_response.startswith('```'):
                                cleaned_response = cleaned_response[3:]
                            if cleaned_response.endswith('```'):
                                cleaned_response = cleaned_response[:-3]
                            cleaned_response = cleaned_response.strip()
                            
                            # Parse JSON response
                            response_data = json.loads(cleaned_response)
                            
                            # Check if response is a dict
                            if not isinstance(response_data, dict):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'gulf_maids_wrong_tool',
                                    'error_reason': 'UNEXPECTED_FORMAT',
                                    'description': f'{prompt_type} analysis - JSON response is not a dict'
                                }
                                continue
                            
                            # Check Tool Calls Summary
                            tool_calls_summary = response_data.get('Tool Calls Summary', {})
                            if not isinstance(tool_calls_summary, dict):
                                result['has_assessment_errors'] = True
                                result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'gulf_maids_wrong_tool',
                                    'error_reason': 'INVALID_TOOL_CALLS_SUMMARY_FORMAT',
                                    'description': f'{prompt_type} analysis - Tool Calls Summary is not a dict'
                                }
                                continue
                            
                            # Check if any tool has Wrong Calls > 0
                            has_wrong_tool = False
                            wrong_tool_count = 0
                            for tool_name, tool_data in tool_calls_summary.items():
                                if isinstance(tool_data, dict):
                                    wrong_calls = tool_data.get('Wrong Calls', '0')
                                    # Convert to int, handle both string and int types
                                    try:
                                        wrong_calls_int = int(str(wrong_calls))
                                        if wrong_calls_int > 0:
                                            has_wrong_tool = True
                                            wrong_tool_count += wrong_calls_int
                                    except ValueError:
                                        # If conversion fails, skip this tool
                                        continue
                            
                            if has_wrong_tool:
                                if conv_id not in flagged_convs:
                                    flagged_convs[conv_id] = {'count': 0, 'wrong_tool_count': wrong_tool_count}
                                flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError) as e:
                            # Mark as assessment error if JSON parsing fails
                            result['has_assessment_errors'] = True
                            result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                                'criteria': 'gulf_maids_wrong_tool',
                                'error_reason': 'JSON_PARSE_ERROR',
                                'description': f'{prompt_type} analysis JSON parsing failed'
                            }
                            print(f"    ⚠️  Failed to parse Gulf_maids wrong tool data: {llm_response}")
                            continue
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'gulf_maids_wrong_tool',
                            'record_count': data['count'],
                            'wrong_tool_count': data['wrong_tool_count'],
                            'description': f'{prompt_type} analysis flagged - {data["wrong_tool_count"]} wrong tool call(s) detected'
                        }

            elif criteria == 'not_properly_called_count':
                # BATCH: Check WRONG_TOOL_SUMMARY for not_properly_called_count > 0
                print(f"    🔍 Checking WRONG_TOOL_SUMMARY for not_properly_called_count > 0")
                
                # STEP 1: First check WRONG_TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)
                print(f"    🔍 Checking WRONG_TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)")
                is_parsed_query = f"""
                SELECT DISTINCT CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.WRONG_TOOL_RAW_DATA
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'FALSE'
                """
                
                is_parsed_results = session.sql(is_parsed_query).collect()
                print(f"    🔍 Found {len(is_parsed_results)} conversations with IS_PARSED = 'FALSE'")
                
                # Mark conversations with IS_PARSED='FALSE' as assessment errors
                for row in is_parsed_results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['has_assessment_errors'] = True
                        result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'not_properly_called_count',
                            'error_reason': 'IS_PARSED_FALSE',
                            'description': f'{prompt_type} analysis parsing failed: IS_PARSED flag set to FALSE'
                        }
                
                # STEP 2: Continue with normal not_properly_called_count logic for remaining conversations
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    not_properly_called_count
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE CONVERSATION_ID IN ('{conv_ids_str}')
                AND not_properly_called_count > 0
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results with wrong tool usage")
                
                # Process results - any record with not_properly_called_count > 0 flags the conversation
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    try:
                        not_properly_called_count = int(row['NOT_PROPERLY_CALLED_COUNT']) if row['NOT_PROPERLY_CALLED_COUNT'] is not None else 0
                    except (ValueError, TypeError):
                        print(f"    ⚠️  Warning: Invalid not_properly_called_count value for {conv_id}: {row['NOT_PROPERLY_CALLED_COUNT']}")
                        not_properly_called_count = 0
                    
                    if conv_id not in flagged_convs:
                        flagged_convs[conv_id] = {
                            'count': 0, 
                            'max_not_properly_called_count': 0,
                            'total_not_properly_called_count': 0
                        }
                    
                    flagged_convs[conv_id]['count'] += 1
                    flagged_convs[conv_id]['total_not_properly_called_count'] += not_properly_called_count
                    if not_properly_called_count > flagged_convs[conv_id]['max_not_properly_called_count']:
                        flagged_convs[conv_id]['max_not_properly_called_count'] = not_properly_called_count
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'not_properly_called_count',
                            'record_count': data['count'],
                            'max_not_properly_called_count': data['max_not_properly_called_count'],
                            'total_not_properly_called_count': data['total_not_properly_called_count'],
                            'description': f'{prompt_type} analysis flagged - tools not properly called (total count: {data["total_not_properly_called_count"]})'
                        }

            elif criteria == 'missed_called_count':
                # BATCH: Check MISSING_TOOL_SUMMARY for missed_called_count > 0
                print(f"    🔍 Checking MISSING_TOOL_SUMMARY for missed_called_count > 0")
                
                # STEP 1: First check MISSING_TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)
                print(f"    🔍 Checking MISSING_TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)")
                is_parsed_query = f"""
                SELECT DISTINCT CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.MISSING_TOOL_RAW_DATA
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'FALSE'
                """
                
                is_parsed_results = session.sql(is_parsed_query).collect()
                print(f"    🔍 Found {len(is_parsed_results)} conversations with IS_PARSED = 'FALSE'")
                
                # Mark conversations with IS_PARSED='FALSE' as assessment errors
                for row in is_parsed_results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['has_assessment_errors'] = True
                        result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missed_called_count',
                            'error_reason': 'IS_PARSED_FALSE',
                            'description': f'{prompt_type} analysis parsing failed: IS_PARSED flag set to FALSE'
                        }
                
                # STEP 2: Continue with normal missed_called_count logic for remaining conversations
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    missed_called_count
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE CONVERSATION_ID IN ('{conv_ids_str}')
                AND missed_called_count > 0
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results with missed tool calls")
                
                # Process results - any record with missed_called_count > 0 flags the conversation
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    try:
                        missed_called_count = int(row['MISSED_CALLED_COUNT']) if row['MISSED_CALLED_COUNT'] is not None else 0
                    except (ValueError, TypeError):
                        print(f"    ⚠️  Warning: Invalid missed_called_count value for {conv_id}: {row['MISSED_CALLED_COUNT']}")
                        missed_called_count = 0
                    
                    if conv_id not in flagged_convs:
                        flagged_convs[conv_id] = {
                            'count': 0, 
                            'max_missed_called_count': 0,
                            'total_missed_called_count': 0
                        }
                    
                    flagged_convs[conv_id]['count'] += 1
                    flagged_convs[conv_id]['total_missed_called_count'] += missed_called_count
                    if missed_called_count > flagged_convs[conv_id]['max_missed_called_count']:
                        flagged_convs[conv_id]['max_missed_called_count'] = missed_called_count
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missed_called_count',
                            'record_count': data['count'],
                            'max_missed_called_count': data['max_missed_called_count'],
                            'total_missed_called_count': data['total_missed_called_count'],
                            'description': f'{prompt_type} analysis flagged - tool calls missed (total count: {data["total_missed_called_count"]})'
                        }

            elif criteria == 'wrong_tool_percentage':
                # BATCH: Check TOOL_SUMMARY for WRONG_TOOL_PERCENTAGE > 0 (CC_Sales only)
                print(f"    🔍 Checking TOOL_SUMMARY for WRONG_TOOL_PERCENTAGE > 0 (CC_Sales)")
                
                # STEP 1: First check TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)
                print(f"    🔍 Checking TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)")
                is_parsed_query = f"""
                SELECT DISTINCT CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.TOOL_RAW_DATA
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'FALSE'
                """
                
                is_parsed_results = session.sql(is_parsed_query).collect()
                print(f"    🔍 Found {len(is_parsed_results)} conversations with IS_PARSED = 'FALSE'")
                
                # Mark conversations with IS_PARSED='FALSE' as assessment errors
                for row in is_parsed_results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['has_assessment_errors'] = True
                        result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'wrong_tool_percentage',
                            'error_reason': 'IS_PARSED_FALSE',
                            'description': f'{prompt_type} analysis parsing failed: IS_PARSED flag set to FALSE'
                        }
                
                # STEP 2: Continue with normal wrong_tool_percentage logic for remaining conversations
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    WRONG_TOOL_PERCENTAGE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE CONVERSATION_ID IN ('{conv_ids_str}')
                AND WRONG_TOOL_PERCENTAGE > 0
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results with wrong tool percentage > 0")
                
                # Process results - any record with WRONG_TOOL_PERCENTAGE > 0 flags the conversation
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    try:
                        wrong_tool_percentage = float(row['WRONG_TOOL_PERCENTAGE']) if row['WRONG_TOOL_PERCENTAGE'] is not None else 0.0
                    except (ValueError, TypeError):
                        print(f"    ⚠️  Warning: Invalid WRONG_TOOL_PERCENTAGE value for {conv_id}: {row['WRONG_TOOL_PERCENTAGE']}")
                        wrong_tool_percentage = 0.0
                    
                    if conv_id not in flagged_convs:
                        flagged_convs[conv_id] = {
                            'count': 0, 
                            'max_wrong_tool_percentage': 0.0,
                            'total_wrong_tool_percentage': 0.0
                        }
                    
                    flagged_convs[conv_id]['count'] += 1
                    flagged_convs[conv_id]['total_wrong_tool_percentage'] += wrong_tool_percentage
                    if wrong_tool_percentage > flagged_convs[conv_id]['max_wrong_tool_percentage']:
                        flagged_convs[conv_id]['max_wrong_tool_percentage'] = wrong_tool_percentage
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'wrong_tool_percentage',
                            'record_count': data['count'],
                            'max_wrong_tool_percentage': data['max_wrong_tool_percentage'],
                            'total_wrong_tool_percentage': data['total_wrong_tool_percentage'],
                            'description': f'{prompt_type} analysis flagged - wrong tool percentage detected (max: {data["max_wrong_tool_percentage"]}%)'
                        }

            elif criteria == 'missing_tool_percentage':
                # BATCH: Check TOOL_SUMMARY for MISSING_TOOL_PERCENTAGE > 0 (CC_Sales only)
                print(f"    🔍 Checking TOOL_SUMMARY for MISSING_TOOL_PERCENTAGE > 0 (CC_Sales)")
                
                # STEP 1: First check TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)
                print(f"    🔍 Checking TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)")
                is_parsed_query = f"""
                SELECT DISTINCT CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.TOOL_RAW_DATA
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'FALSE'
                """
                
                is_parsed_results = session.sql(is_parsed_query).collect()
                print(f"    🔍 Found {len(is_parsed_results)} conversations with IS_PARSED = 'FALSE'")
                
                # Mark conversations with IS_PARSED='FALSE' as assessment errors
                for row in is_parsed_results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['has_assessment_errors'] = True
                        result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missing_tool_percentage',
                            'error_reason': 'IS_PARSED_FALSE',
                            'description': f'{prompt_type} analysis parsing failed: IS_PARSED flag set to FALSE'
                        }
                
                # STEP 2: Continue with normal missing_tool_percentage logic for remaining conversations
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    MISSING_TOOL_PERCENTAGE
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE CONVERSATION_ID IN ('{conv_ids_str}')
                AND MISSING_TOOL_PERCENTAGE > 0
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results with missing tool percentage > 0")
                
                # Process results - any record with MISSING_TOOL_PERCENTAGE > 0 flags the conversation
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    try:
                        missing_tool_percentage = float(row['MISSING_TOOL_PERCENTAGE']) if row['MISSING_TOOL_PERCENTAGE'] is not None else 0.0
                    except (ValueError, TypeError):
                        print(f"    ⚠️  Warning: Invalid MISSING_TOOL_PERCENTAGE value for {conv_id}: {row['MISSING_TOOL_PERCENTAGE']}")
                        missing_tool_percentage = 0.0
                    
                    if conv_id not in flagged_convs:
                        flagged_convs[conv_id] = {
                            'count': 0, 
                            'max_missing_tool_percentage': 0.0,
                            'total_missing_tool_percentage': 0.0
                        }
                    
                    flagged_convs[conv_id]['count'] += 1
                    flagged_convs[conv_id]['total_missing_tool_percentage'] += missing_tool_percentage
                    if missing_tool_percentage > flagged_convs[conv_id]['max_missing_tool_percentage']:
                        flagged_convs[conv_id]['max_missing_tool_percentage'] = missing_tool_percentage
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missing_tool_percentage',
                            'record_count': data['count'],
                            'max_missing_tool_percentage': data['max_missing_tool_percentage'],
                            'total_missing_tool_percentage': data['total_missing_tool_percentage'],
                            'description': f'{prompt_type} analysis flagged - missing tool percentage detected (max: {data["max_missing_tool_percentage"]}%)'
                        }
                        
            elif criteria == 'wrong_tool_pct':
                # BATCH: Check TOOL_EVAL_SUMMARY for WRONG_PCT > 0 (Generic tool evaluation)
                print(f"    🔍 Checking TOOL_EVAL_SUMMARY for WRONG_PCT > 0")
                
                # STEP 1: First check TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)
                print(f"    🔍 Checking TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)")
                is_parsed_query = f"""
                SELECT DISTINCT CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.TOOL_RAW_DATA
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'FALSE'
                """
                
                is_parsed_results = session.sql(is_parsed_query).collect()
                print(f"    🔍 Found {len(is_parsed_results)} conversations with IS_PARSED = 'FALSE'")
                
                # Mark conversations with IS_PARSED='FALSE' as assessment errors
                for row in is_parsed_results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['has_assessment_errors'] = True
                        result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'wrong_tool_pct',
                            'error_reason': 'IS_PARSED_FALSE',
                            'description': f'{prompt_type} analysis parsing failed: IS_PARSED flag set to FALSE'
                        }
                
                # STEP 2: Continue with normal wrong_tool_pct logic for remaining conversations
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    WRONG_PCT
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE CONVERSATION_ID IN ('{conv_ids_str}')
                AND WRONG_PCT > 0
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results with WRONG_PCT > 0")
                
                # Process results - any record with WRONG_PCT > 0 flags the conversation
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    try:
                        wrong_pct = float(row['WRONG_PCT']) if row['WRONG_PCT'] is not None else 0.0
                    except (ValueError, TypeError):
                        print(f"    ⚠️  Warning: Invalid WRONG_PCT value for {conv_id}: {row['WRONG_PCT']}")
                        wrong_pct = 0.0
                    
                    if conv_id not in flagged_convs:
                        flagged_convs[conv_id] = {
                            'count': 0, 
                            'max_wrong_pct': 0.0,
                            'total_wrong_pct': 0.0
                        }
                    
                    flagged_convs[conv_id]['count'] += 1
                    flagged_convs[conv_id]['total_wrong_pct'] += wrong_pct
                    if wrong_pct > flagged_convs[conv_id]['max_wrong_pct']:
                        flagged_convs[conv_id]['max_wrong_pct'] = wrong_pct
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'wrong_tool_pct',
                            'record_count': data['count'],
                            'max_wrong_pct': data['max_wrong_pct'],
                            'total_wrong_pct': data['total_wrong_pct'],
                            'description': f'{prompt_type} analysis flagged - wrong tool detected (max: {data["max_wrong_pct"]}%)'
                        }

            elif criteria == 'missing_tool_pct':
                # BATCH: Check TOOL_EVAL_SUMMARY for MISSING_PCT > 0 (Generic tool evaluation)
                print(f"    🔍 Checking TOOL_EVAL_SUMMARY for MISSING_PCT > 0")
                
                # STEP 1: First check TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)
                print(f"    🔍 Checking TOOL_RAW_DATA for IS_PARSED = 'FALSE' (parsing failures)")
                is_parsed_query = f"""
                SELECT DISTINCT CONVERSATION_ID
                FROM LLM_EVAL.PUBLIC.TOOL_RAW_DATA
                WHERE DATE(DATE) = DATE('{target_date}')
                {get_department_filter(department_name)}
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND IS_PARSED = 'FALSE'
                """
                
                is_parsed_results = session.sql(is_parsed_query).collect()
                print(f"    🔍 Found {len(is_parsed_results)} conversations with IS_PARSED = 'FALSE'")
                
                # Mark conversations with IS_PARSED='FALSE' as assessment errors
                for row in is_parsed_results:
                    conv_id = row['CONVERSATION_ID']
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['has_assessment_errors'] = True
                        result['assessment_error_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missing_tool_pct',
                            'error_reason': 'IS_PARSED_FALSE',
                            'description': f'{prompt_type} analysis parsing failed: IS_PARSED flag set to FALSE'
                        }
                
                # STEP 2: Continue with normal missing_tool_pct logic for remaining conversations
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    MISSING_PCT
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE CONVERSATION_ID IN ('{conv_ids_str}')
                AND MISSING_PCT > 0
                """
                
                results = session.sql(query).collect()
                print(f"    🔍 Found {len(results)} results with MISSING_PCT > 0")
                
                # Process results - any record with MISSING_PCT > 0 flags the conversation
                flagged_convs = {}
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    try:
                        missing_pct = float(row['MISSING_PCT']) if row['MISSING_PCT'] is not None else 0.0
                    except (ValueError, TypeError):
                        print(f"    ⚠️  Warning: Invalid MISSING_PCT value for {conv_id}: {row['MISSING_PCT']}")
                        missing_pct = 0.0
                    
                    if conv_id not in flagged_convs:
                        flagged_convs[conv_id] = {
                            'count': 0, 
                            'max_missing_pct': 0.0,
                            'total_missing_pct': 0.0
                        }
                    
                    flagged_convs[conv_id]['count'] += 1
                    flagged_convs[conv_id]['total_missing_pct'] += missing_pct
                    if missing_pct > flagged_convs[conv_id]['max_missing_pct']:
                        flagged_convs[conv_id]['max_missing_pct'] = missing_pct
                
                # Update flagging results for affected conversations
                for conv_id, data in flagged_convs.items():
                    if conv_id in all_flagging_results:
                        result = all_flagging_results[conv_id]
                        result['is_flagged'] = True
                        result['specialized_prompt_flagged'] = True
                        result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                        result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                            'criteria': 'missing_tool_pct',
                            'record_count': data['count'],
                            'max_missing_pct': data['max_missing_pct'],
                            'total_missing_pct': data['total_missing_pct'],
                            'description': f'{prompt_type} analysis flagged - missing tool detected (max: {data["max_missing_pct"]}%)'
                        }
                        
        except Exception as e:
            print(f"    ⚠️  Error batch checking {table_name}: {str(e)}")
            continue
    
    print(f"    ✅ Batch flagging check completed for {len(conversation_ids)} conversations")
    return all_flagging_results

def check_conversation_flagged_status(session, conversation_id, department_name, target_date):
    """
    Legacy function for single conversation checking (kept for compatibility)
    NOTE: Use batch version for better performance
    """
    batch_results = check_all_conversations_flagged_status_batch(
        session, [conversation_id], department_name, target_date
    )
    return batch_results.get(conversation_id, {
        'conversation_id': conversation_id,
        'is_flagged': False,
        'flagging_sources': [],
        'flagging_details': {},
        'sa_nps_flagged': False,
        'specialized_prompt_flagged': False
    })

def debug_conversation_flagging(all_flagging_results, conversation_id):
    """
    Debug why a specific conversation was flagged
    
    Args:
        all_flagging_results: Dictionary with all flagging results
        conversation_id: The conversation ID to debug
    """
    if conversation_id not in all_flagging_results:
        print(f"❌ Conversation {conversation_id} not found in results")
        return
    
    result = all_flagging_results[conversation_id]
    
    print(f"\n🔍 DEBUGGING CONVERSATION: {conversation_id}")
    print(f"    📊 Is Flagged: {result['is_flagged']}")
    print(f"    🎯 SA NPS Flagged: {result['sa_nps_flagged']}")
    print(f"    🎯 Specialized Prompt Flagged: {result['specialized_prompt_flagged']}")
    print(f"    ⚠️  Has Assessment Errors: {result['has_assessment_errors']}")
    
    if result['flagging_sources']:
        print(f"    📋 Flagging Sources ({len(result['flagging_sources'])}):")
        for source in result['flagging_sources']:
            print(f"        - {source}")
    
    if result['flagging_details']:
        print(f"    📝 Flagging Details:")
        for source, details in result['flagging_details'].items():
            print(f"        🎯 {source}:")
            print(f"            - Criteria: {details['criteria']}")
            if 'record_count' in details:
                print(f"            - Record Count: {details['record_count']}")
            if 'description' in details:
                print(f"            - Description: {details['description']}")
            # Print any other specific values
            for key, value in details.items():
                if key not in ['criteria', 'record_count', 'description']:
                    print(f"            - {key}: {value}")
    
    if result['assessment_error_details']:
        print(f"    ⚠️  Assessment Error Details:")
        for source, error_details in result['assessment_error_details'].items():
            print(f"        🚨 {source}:")
            print(f"            - Criteria: {error_details['criteria']}")
            print(f"            - Error Reason: {error_details['error_reason']}")
            print(f"            - Description: {error_details['description']}")

def analyze_department_clean_chats(session, department_name, target_date=None):
    """
    Analyze clean chats for a single department using LLM_JUDGE filtering methods
    
    Args:
        session: Snowflake session
        department_name: Department name to analyze
        target_date: Target date for analysis
        
    Returns:
        Dictionary with analysis results
    """
    print(f"\n🧹 CLEAN CHATS ANALYSIS: {department_name}")
    print("=" * 50)
    
    # Set target date if not provided (same logic as LLM_JUDGE)
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"📅 Target date: {target_date}")
    
    try:
        # Step 1: Use delay_analysis_raw_data table to get conversation IDs
        print(f"📊 Step 1: Loading filtered conversations from delay_analysis_raw_data table...")
        filtered_df, success = process_department_phase1_from_delay_table(
            session, department_name, target_date
        )
        
        if not success or filtered_df.empty:
            print(f"    ❌ No filtered data from Phase 1")
            return {
                'success': False,
                'error': 'No filtered data from Phase 1',
                'department': department_name,
                'target_date': target_date
            }
        
        conversation_ids = filtered_df['CONVERSATION_ID'].unique()
        total_conversations = len(conversation_ids)
        
        print(f"    ✅ Found {total_conversations} conversations to analyze")
        
        # Step 2: Check flagging status for ALL conversations in BATCH (OPTIMIZED)
        print(f"🔍 Step 2: Batch checking flagging status for all conversations...")
        
        # BATCH: Check all conversations at once
        all_flagging_results = check_all_conversations_flagged_status_batch(
            session, conversation_ids.tolist(), department_name, target_date
        )
        
        # DEBUG: Uncomment the line below to debug a specific conversation ID
        # debug_conversation_flagging(all_flagging_results, 'CH7140e5a2e61e4ee49f7379819c685a2e')
        
        clean_conversations = []
        flagged_conversations = []
        not_assessed_conversations = []
        flagging_breakdown = {
            'sa_nps_flagged': 0,
            'specialized_prompt_flagged': 0,
            'both_flagged': 0,
            'flagging_sources': {}
        }
        
        conversation_details = []
        
        print(f"    📋 Processing flagging results for {total_conversations} conversations...")
        
        for conv_id in conversation_ids:
            # Get conversation metadata from filtered_df
            conv_data = filtered_df[filtered_df['CONVERSATION_ID'] == conv_id].iloc[0]
            customer_name = conv_data.get('CUSTOMER_NAME', '') if pd.notna(conv_data.get('CUSTOMER_NAME')) else ''
            agent_names = conv_data.get('AGENT_NAMES', '') if pd.notna(conv_data.get('AGENT_NAMES')) else ''
            last_skill = conv_data.get('LAST_SKILL', '') if pd.notna(conv_data.get('LAST_SKILL')) else ''
            
            # Get flagging status from batch results
            flagging_status = all_flagging_results.get(conv_id, {
                'conversation_id': conv_id,
                'is_flagged': False,
                'flagging_sources': [],
                'flagging_details': {},
                'sa_nps_flagged': False,
                'specialized_prompt_flagged': False,
                'has_assessment_errors': False,
                'assessment_error_details': {}
            })
            
            # Determine overall conversation status
            if flagging_status.get('has_assessment_errors', False):
                is_clean_status = 'NOT_ASSESSED'
            elif flagging_status['is_flagged']:
                is_clean_status = 'FALSE'
            else:
                is_clean_status = 'TRUE'
            
            # Create conversation detail record
            conversation_detail = {
                'conversation_id': conv_id,
                'customer_name': str(customer_name),
                'agent_names': str(agent_names),
                'last_skill': str(last_skill),
                'is_clean': is_clean_status,
                'flagging_sources': ','.join(flagging_status['flagging_sources']),
                'flagging_details': json.dumps(flagging_status['flagging_details']),
                'sa_nps_flagged': flagging_status['sa_nps_flagged'],
                'specialized_prompt_flagged': flagging_status['specialized_prompt_flagged'],
                'has_assessment_errors': flagging_status.get('has_assessment_errors', False),
                'assessment_error_details': json.dumps(flagging_status.get('assessment_error_details', {}))
            }
            conversation_details.append(conversation_detail)
            
            # Categorize conversation
            if is_clean_status == 'NOT_ASSESSED':
                not_assessed_conversations.append(conv_id)
            elif is_clean_status == 'FALSE':
                flagged_conversations.append(conv_id)
                
                # Update flagging breakdown
                if flagging_status['sa_nps_flagged'] and flagging_status['specialized_prompt_flagged']:
                    flagging_breakdown['both_flagged'] += 1
                elif flagging_status['sa_nps_flagged']:
                    flagging_breakdown['sa_nps_flagged'] += 1
                elif flagging_status['specialized_prompt_flagged']:
                    flagging_breakdown['specialized_prompt_flagged'] += 1
                
                # Track flagging sources
                for source in flagging_status['flagging_sources']:
                    flagging_breakdown['flagging_sources'][source] = flagging_breakdown['flagging_sources'].get(source, 0) + 1
                    
            else:  # is_clean_status == 'TRUE'
                clean_conversations.append(conv_id)
        
        # Step 3: Calculate summary statistics
        clean_count = len(clean_conversations)
        flagged_count = len(flagged_conversations)
        not_assessed_count = len(not_assessed_conversations)
        
        # Calculate percentages based on assessable conversations (exclude NOT_ASSESSED)
        assessable_conversations = total_conversations - not_assessed_count
        clean_percentage = (clean_count / assessable_conversations * 100) if assessable_conversations > 0 else 0
        
        # Create summary results
        summary_results = {
            'success': True,
            'department': department_name,
            'target_date': target_date,
            'analysis_timestamp': datetime.now().isoformat(),
            'total_conversations': total_conversations,
            'clean_conversations': clean_count,
            'flagged_conversations': flagged_count,
            'not_assessed_conversations': not_assessed_count,
            'assessable_conversations': assessable_conversations,
            'clean_percentage': round(clean_percentage, 2),
            'flagged_by_sa_nps': flagging_breakdown['sa_nps_flagged'],
            'flagged_by_specialized_prompts': flagging_breakdown['specialized_prompt_flagged'],
            'flagged_by_both': flagging_breakdown['both_flagged'],
            'flagging_breakdown': flagging_breakdown,
            'conversation_details': conversation_details
        }
        
        # Print summary
        print(f"\n📊 CLEAN CHATS SUMMARY - {department_name}")
        print(f"    💬 Total conversations: {total_conversations:,}")
        print(f"    ✅ Clean conversations: {clean_count:,} ({clean_percentage:.1f}%)")
        print(f"    🚩 Flagged conversations: {flagged_count:,}")
        print(f"       - By SA NPS=1: {flagging_breakdown['sa_nps_flagged']:,}")
        print(f"       - By specialized prompts: {flagging_breakdown['specialized_prompt_flagged']:,}")
        print(f"       - By both: {flagging_breakdown['both_flagged']:,}")
        
        if flagging_breakdown['flagging_sources']:
            print(f"    📋 Top flagging sources:")
            sorted_sources = sorted(flagging_breakdown['flagging_sources'].items(), key=lambda x: x[1], reverse=True)
            for source, count in sorted_sources[:5]:  # Top 5
                print(f"       - {source}: {count}")
        
        return summary_results
        
    except Exception as e:
        error_msg = f"Clean chats analysis failed for {department_name}: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'department': department_name,
            'target_date': target_date,
            'traceback': str(e)
        }

def analyze_all_departments_clean_chats(session, target_date=None, department_filter=None):
    """
    Analyze clean chats for all departments
    
    Args:
        session: Snowflake session
        target_date: Target date for analysis
        department_filter: Optional specific department to process
        
    Returns:
        Analysis results for all departments
    """
    print("\n🧹 CLEAN CHATS ANALYSIS: ALL DEPARTMENTS")
    print("=" * 60)
    
    # Set target date if not provided
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"📅 Target date: {target_date}")
    
    if department_filter:
        print(f"🎯 Department filter: {department_filter}")
    
    print("=" * 60)
    
    departments_config = get_clean_chats_departments_config()
    department_results = {}
    
    # Get list of departments to process
    departments_to_process = [department_filter] if department_filter else list(departments_config.keys())
    
    total_departments = len(departments_to_process)
    processed_departments = 0
    successful_departments = 0
    
    # Overall statistics
    overall_stats = {
        'total_conversations': 0,
        'total_clean': 0,
        'total_flagged': 0,
        'departments_processed': 0,
        'departments_successful': 0
    }
    
    for department_name in departments_to_process:
        if department_name not in departments_config:
            print(f"⚠️  Department {department_name} not found in configuration")
            continue
            
        try:
            # Analyze department
            dept_results = analyze_department_clean_chats(session, department_name, target_date)
            department_results[department_name] = dept_results
            processed_departments += 1
            
            if dept_results['success']:
                successful_departments += 1
                # Add to overall statistics
                overall_stats['total_conversations'] += dept_results['total_conversations']
                overall_stats['total_clean'] += dept_results['clean_conversations']
                overall_stats['total_flagged'] += dept_results['flagged_conversations']
            
        except Exception as e:
            error_msg = f"Clean chats analysis failed: {str(e)}"
            print(f"  ❌ {department_name}: {error_msg}")
            department_results[department_name] = {
                'success': False,
                'error': error_msg,
                'department': department_name,
                'target_date': target_date
            }
            processed_departments += 1
    
    # Update overall statistics
    overall_stats['departments_processed'] = processed_departments
    overall_stats['departments_successful'] = successful_departments
    
    # Calculate overall clean percentage
    overall_clean_percentage = (overall_stats['total_clean'] / overall_stats['total_conversations'] * 100) if overall_stats['total_conversations'] > 0 else 0
    
    # Generate final summary
    summary = f"""
🧹 CLEAN CHATS ANALYSIS - SUMMARY
{'=' * 50}
📅 Date: {target_date}
🏢 Departments processed: {processed_departments}/{total_departments}
✅ Successful departments: {successful_departments}/{processed_departments}

📊 OVERALL METRICS:
   💬 Total conversations: {overall_stats['total_conversations']:,}
   ✅ Clean conversations: {overall_stats['total_clean']:,} ({overall_clean_percentage:.1f}%)
   🚩 Flagged conversations: {overall_stats['total_flagged']:,}

🌟 Clean Chats Analysis Complete!
   Ready for review and reporting
"""
    
    print(summary)
    
    return {
        'summary': summary,
        'department_results': department_results,
        'overall_statistics': overall_stats,
        'overall_clean_percentage': overall_clean_percentage,
        'target_date': target_date,
        'analysis_timestamp': datetime.now().isoformat()
    }
