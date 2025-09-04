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
    get_department_flagging_tables
)


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
        AND department = '{department_name}'
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
            'specialized_prompt_flagged': False
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
                AND DEPARTMENT = '{department_name}'
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                """
                
                results = session.sql(query).collect()
                
                for row in results:
                    conv_id = row['CONVERSATION_ID']
                    llm_response = row['LLM_RESPONSE']
                    
                    if llm_response and conv_id in all_flagging_results:
                        # Parse JSON response to get NPS score
                        try:
                            response_data = json.loads(llm_response)
                            nps_score = response_data.get('NPS_score', 0)
                            if nps_score == 1:
                                result = all_flagging_results[conv_id]
                                result['is_flagged'] = True
                                result['sa_nps_flagged'] = True
                                result['flagging_sources'].append(f"{table_name}_{prompt_type}")
                                result['flagging_details'][f"{table_name}_{prompt_type}"] = {
                                    'criteria': 'nps_score_1',
                                    'nps_score': nps_score,
                                    'description': 'SA analysis with NPS score = 1'
                                }
                        except (json.JSONDecodeError, KeyError):
                            continue
                            
            elif criteria == 'contains_yes':
                # BATCH: Check specialized prompt tables for ALL conversations with "YES"
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                AND DEPARTMENT = '{department_name}'
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                AND UPPER(LLM_RESPONSE) LIKE '%YES%'
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
                            'criteria': 'contains_yes',
                            'record_count': count,
                            'description': f'{prompt_type} analysis flagged with YES response'
                        }
                        
            elif criteria == 'contains_true':
                # BATCH: Check specialized prompt tables for ALL conversations with "TRUE"
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                AND DEPARTMENT = '{department_name}'
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                AND UPPER(LLM_RESPONSE) LIKE '%TRUE%'
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
                            'criteria': 'contains_true',
                            'record_count': count,
                            'description': f'{prompt_type} analysis flagged with TRUE response'
                        }
                        
            elif criteria == 'contains_rogue_answer':
                # BATCH: Check specialized prompt tables for ALL conversations with "RogueAnswer"
                query = f"""
                SELECT 
                    CONVERSATION_ID,
                    LLM_RESPONSE,
                    PROCESSING_STATUS
                FROM LLM_EVAL.PUBLIC.{table_name}
                WHERE DATE(DATE) = DATE('{target_date}')
                AND DEPARTMENT = '{department_name}'
                AND PROMPT_TYPE = '{prompt_type}'
                AND CONVERSATION_ID IN ('{conv_ids_str}')
                AND PROCESSING_STATUS = 'COMPLETED'
                AND UPPER(LLM_RESPONSE) LIKE '%ROGUEANSWER%'
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
                AND DEPARTMENT = '{department_name}'
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
                AND DEPARTMENT = '{department_name}'
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
                    
                    if llm_response and conv_id in all_flagging_results:
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
                                print("switch to ClarificationMessagesTotal")
                                clarification_count = response_data.get('ClarificationMessages')
                                print(f"    🔍 Clarification count: {clarification_count}")
                            # Convert to int and check if > 0
                            if clarification_count is not None:
                                try:
                                    clarification_count = int(clarification_count)
                                    if clarification_count > 0:
                                        if conv_id not in flagged_convs:
                                            flagged_convs[conv_id] = {'count': 0, 'clarification_count': clarification_count}
                                        flagged_convs[conv_id]['count'] += 1
                                        
                                except (ValueError, TypeError):
                                    # Skip if clarification_count is not a valid number
                                    continue
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Skip if JSON parsing fails
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
                AND DEPARTMENT = '{department_name}'
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
                    
                    if llm_response and conv_id in all_flagging_results:
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
                            print(f"    🔍 could_avoid_visit value: {could_avoid_visit}")
                            
                            # Check if could_avoid_visit is true (boolean or string 'true')
                            if could_avoid_visit is not None:
                                if (isinstance(could_avoid_visit, bool) and could_avoid_visit) or \
                                   (isinstance(could_avoid_visit, str) and could_avoid_visit.lower() == 'true'):
                                    if conv_id not in flagged_convs:
                                        flagged_convs[conv_id] = {'count': 0, 'avoid_visit_value': could_avoid_visit}
                                    flagged_convs[conv_id]['count'] += 1
                                    
                        except (json.JSONDecodeError, KeyError):
                            # Skip if JSON parsing fails
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
        
        clean_conversations = []
        flagged_conversations = []
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
                'specialized_prompt_flagged': False
            })
            
            # Create conversation detail record
            conversation_detail = {
                'conversation_id': conv_id,
                'customer_name': str(customer_name),
                'agent_names': str(agent_names),
                'last_skill': str(last_skill),
                'is_clean': not flagging_status['is_flagged'],
                'flagging_sources': ','.join(flagging_status['flagging_sources']),
                'flagging_details': json.dumps(flagging_status['flagging_details'])
            }
            conversation_details.append(conversation_detail)
            
            # Categorize conversation
            if flagging_status['is_flagged']:
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
                    
            else:
                clean_conversations.append(conv_id)
        
        # Step 3: Calculate summary statistics
        clean_count = len(clean_conversations)
        flagged_count = len(flagged_conversations)
        clean_percentage = (clean_count / total_conversations * 100) if total_conversations > 0 else 0
        
        # Create summary results
        summary_results = {
            'success': True,
            'department': department_name,
            'target_date': target_date,
            'analysis_timestamp': datetime.now().isoformat(),
            'total_conversations': total_conversations,
            'clean_conversations': clean_count,
            'flagged_conversations': flagged_count,
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
