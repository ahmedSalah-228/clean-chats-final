"""
Clean Chats Storage Module
Handles saving clean chats analysis results to Snowflake tables
"""

import sys
import os
import json
from datetime import datetime

# Add LLM_JUDGE to path for imports
llm_judge_path = "/Users/ahmedsalah/Projects/Clean Chats/LLM_JUDGE"
if llm_judge_path not in sys.path:
    sys.path.append(llm_judge_path)

from clean_chats_config import (
    get_clean_chats_summary_schema,
    get_clean_chats_raw_data_schema,
    get_department_flagging_applicability,
    get_flagging_system_mapping,
    get_llm_response_based_criteria,
    get_table_existence_based_criteria
)

def extract_flagging_source_counts(flagging_breakdown_dict):
    """
    Extract individual flagging source counts from flagging_breakdown
    Maps source keys to standardized column names
    
    Args:
        flagging_breakdown_dict: Dictionary with flagging_sources
        
    Returns:
        Dictionary with individual count columns (all 13 metrics, defaulting to 0)
    """
    # Initialize all counts to 0
    counts = {
        'FALSE_PROMISES_COUNT': 0,
        'LEGAL_ALIGNMENT_COUNT': 0,
        'REPETITION_COUNT': 0,
        'UNRESPONSIVE_COUNT': 0,
        'REPORTED_ISSUES_COUNT': 0,
        'INTERVENTIONS_COUNT': 0,
        'MISPRESCRIPTION_COUNT': 0,
        'UNNECESSARY_CLINIC_COUNT': 0,
        'CLARITY_SCORE_COUNT': 0,
        'WRONG_TOOL_COUNT': 0,
        'MISSED_TOOL_CALL_COUNT': 0,
        'UNCLEAR_POLICY_COUNT': 0,
        'MISSING_POLICY_COUNT': 0,
        'WRONG_ANSWER_COUNT': 0
    }
    
    # Get mapping from prompt_type to standardized names
    system_mapping = get_flagging_system_mapping()
    
    # Extract counts from flagging_sources
    flagging_sources = flagging_breakdown_dict.get('flagging_sources', {})
    
    for source_key, count in flagging_sources.items():
        # Extract prompt_type from source key (e.g., "FALSE_PROMISES_RAW_DATA_false_promises" -> "false_promises")
        # The prompt_type is typically after the last underscore before the table name
        # We'll look for known prompt types in the key
        source_lower = source_key.lower()
        
        # Map source to standardized column name
        for prompt_type, standard_name in system_mapping.items():
            if prompt_type in source_lower:
                column_name = f"{standard_name}_COUNT"
                if column_name in counts:
                    counts[column_name] += count  # Sum if multiple sources map to same metric
                break
    
    return counts

def create_clean_chats_tables(session):
    """
    Create clean chats summary and raw data tables if they don't exist
    
    Args:
        session: Snowflake session
        
    Returns:
        Success status
    """
    print("🗄️  Creating clean chats tables...")
    
    try:
        # Create summary table
        summary_schema = get_clean_chats_summary_schema()
        summary_columns = []
        for col_name, col_type in summary_schema.items():
            summary_columns.append(f"{col_name} {col_type}")
        
        summary_table_sql = f"""
        CREATE TABLE IF NOT EXISTS LLM_EVAL.PUBLIC.CLEAN_CHATS_SUMMARY (
            {', '.join(summary_columns)}
        )
        """
        
        session.sql(summary_table_sql).collect()
        print("    ✅ CLEAN_CHATS_SUMMARY table created/verified")
        
        # Create raw data table (new structure)
        raw_data_schema = get_clean_chats_raw_data_schema()
        raw_data_columns = []
        for col_name, col_type in raw_data_schema.items():
            raw_data_columns.append(f"{col_name} {col_type}")
        
        raw_data_table_sql = f"""
        CREATE TABLE IF NOT EXISTS LLM_EVAL.PUBLIC.CLEAN_CHATS_RAW_DATA (
            {', '.join(raw_data_columns)}
        )
        """
        
        session.sql(raw_data_table_sql).collect()
        print("    ✅ CLEAN_CHATS_RAW_DATA table created/verified")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Error creating clean chats tables: {str(e)}")
        return False

def save_clean_chats_summary(session, department_results, target_date):
    """
    Save clean chats summary results to CLEAN_CHATS_SUMMARY table
    
    Args:
        session: Snowflake session
        department_results: Dictionary of department analysis results
        target_date: Target date for analysis
        
    Returns:
        Success status
    """
    print("💾 Saving clean chats summary to database...")
    
    try:
        # Ensure tables exist
        if not create_clean_chats_tables(session):
            return False
        
        # Clear existing data for this date
        cleanup_sql = f"""
        DELETE FROM LLM_EVAL.PUBLIC.CLEAN_CHATS_SUMMARY 
        WHERE DATE = DATE('{target_date}')
        """
        session.sql(cleanup_sql).collect()
        print(f"    🧹 Cleared existing summary data for {target_date}")
        
        # Insert new summary data
        inserted_records = 0
        for department_name, results in department_results.items():
            if results.get('success', False):
                # Prepare data for insertion
                flagging_breakdown_dict = results.get('flagging_breakdown', {})
                flagging_breakdown_json = json.dumps(flagging_breakdown_dict)
                analysis_timestamp = datetime.now()
                
                # Extract individual flagging source counts
                source_counts = extract_flagging_source_counts(flagging_breakdown_dict)
                
                insert_sql = f"""
                INSERT INTO LLM_EVAL.PUBLIC.CLEAN_CHATS_SUMMARY (
                    DATE,
                    DEPARTMENT,
                    TOTAL_CONVERSATIONS,
                    CLEAN_CONVERSATIONS,
                    FLAGGED_CONVERSATIONS,
                    CLEAN_PERCENTAGE,
                    FLAGGED_BY_SA_NPS,
                    FLAGGED_BY_SPECIALIZED_PROMPTS,
                    FLAGGING_BREAKDOWN,
                    FALSE_PROMISES_COUNT,
                    LEGAL_ALIGNMENT_COUNT,
                    REPETITION_COUNT,
                    UNRESPONSIVE_COUNT,
                    REPORTED_ISSUES_COUNT,
                    INTERVENTIONS_COUNT,
                    MISPRESCRIPTION_COUNT,
                    UNNECESSARY_CLINIC_COUNT,
                    CLARITY_SCORE_COUNT,
                    WRONG_TOOL_COUNT,
                    MISSED_TOOL_CALL_COUNT,
                    UNCLEAR_POLICY_COUNT,
                    MISSING_POLICY_COUNT,
                    WRONG_ANSWER_COUNT,
                    ANALYSIS_TIMESTAMP
                ) VALUES (
                    DATE('{target_date}'),
                    '{department_name}',
                    {results['total_conversations']},
                    {results['clean_conversations']},
                    {results['flagged_conversations']},
                    {results['clean_percentage']},
                    {results['flagged_by_sa_nps']},
                    {results['flagged_by_specialized_prompts']},
                    '{flagging_breakdown_json}',
                    {source_counts['FALSE_PROMISES_COUNT']},
                    {source_counts['LEGAL_ALIGNMENT_COUNT']},
                    {source_counts['REPETITION_COUNT']},
                    {source_counts['UNRESPONSIVE_COUNT']},
                    {source_counts['REPORTED_ISSUES_COUNT']},
                    {source_counts['INTERVENTIONS_COUNT']},
                    {source_counts['MISPRESCRIPTION_COUNT']},
                    {source_counts['UNNECESSARY_CLINIC_COUNT']},
                    {source_counts['CLARITY_SCORE_COUNT']},
                    {source_counts['WRONG_TOOL_COUNT']},
                    {source_counts['MISSED_TOOL_CALL_COUNT']},
                    {source_counts['UNCLEAR_POLICY_COUNT']},
                    {source_counts['MISSING_POLICY_COUNT']},
                    {source_counts['WRONG_ANSWER_COUNT']},
                    '{analysis_timestamp}'
                )
                """
                
                session.sql(insert_sql).collect()
                inserted_records += 1
                print(f"    ✅ Saved summary for {department_name}")
        
        print(f"    📊 Inserted {inserted_records} summary records")
        return True
        
    except Exception as e:
        print(f"    ❌ Error saving clean chats summary: {str(e)}")
        return False

def build_individual_flagging_columns(department_name, flagging_details_dict, assessment_error_details_dict, sa_nps_flagged=False, specialized_prompt_flagged=False):
    """
    Build individual flagging column values based on flagging details
    
    Args:
        department_name: Department name
        flagging_details_dict: Dictionary with flagging details from analysis
        assessment_error_details_dict: Dictionary with assessment error details
        sa_nps_flagged: Boolean indicating if SA NPS flagged this conversation
        specialized_prompt_flagged: Boolean indicating if specialized prompts flagged this conversation
        
    Returns:
        Dictionary with individual flagging column values (YES/NO/N_A/NOT_ASSESSED)
    """
    # Get department applicability and system mapping
    applicability = get_department_flagging_applicability().get(department_name, {})
    system_mapping = get_flagging_system_mapping()
    
    # Initialize all flagging columns
    flagging_columns = {
        'FALSE_PROMISES': 'N_A',
        'LEGAL_ALIGNMENT': 'N_A',
        'REPETITION': 'N_A',
        'UNRESPONSIVE': 'N_A',
        'REPORTED_ISSUES': 'N_A',
        'INTERVENTIONS': 'N_A',
        'MISPRESCRIPTION': 'N_A',
        'UNNECESSARY_CLINIC': 'N_A',
        'CLARITY_SCORE': 'N_A',
        'WRONG_TOOL': 'N_A',
        'MISSED_TOOL_CALL': 'N_A',
        'UNCLEAR_POLICY': 'N_A',
        'MISSING_POLICY': 'N_A',
        'WRONG_ANSWER': 'N_A'
    }
    
    # Set N_A or NO based on department applicability
    for system, is_applicable in applicability.items():
        if is_applicable:
            flagging_columns[system] = 'NO'  # Default to NO, will be set to YES/NOT_ASSESSED based on analysis
    
    # First, check for assessment errors and mark as NOT_ASSESSED
    for source_key, error_details in assessment_error_details_dict.items():
        source_lower = source_key.lower()
        
        # Map error sources to flagging systems
        if 'false_promises' in source_lower:
            flagging_columns['FALSE_PROMISES'] = 'NOT_ASSESSED'
        elif 'legal_alignment' in source_lower:
            flagging_columns['LEGAL_ALIGNMENT'] = 'NOT_ASSESSED'
        elif 'misprescription' in source_lower:
            flagging_columns['MISPRESCRIPTION'] = 'NOT_ASSESSED'
        elif 'unnecessary_clinic' in source_lower:
            flagging_columns['UNNECESSARY_CLINIC'] = 'NOT_ASSESSED'
        elif 'clarity_score' in source_lower:
            flagging_columns['CLARITY_SCORE'] = 'NOT_ASSESSED'
        elif 'wrong_tool' in source_lower:
            flagging_columns['WRONG_TOOL'] = 'NOT_ASSESSED'
        elif 'missed_tool_call' in source_lower:
            flagging_columns['MISSED_TOOL_CALL'] = 'NOT_ASSESSED'
        elif 'unclear_policy' in source_lower:
            flagging_columns['UNCLEAR_POLICY'] = 'NOT_ASSESSED'
        elif 'missing_policy' in source_lower:
            flagging_columns['MISSING_POLICY'] = 'NOT_ASSESSED'
        elif 'wrong_answer' in source_lower:
            flagging_columns['WRONG_ANSWER'] = 'NOT_ASSESSED'
    
    # SA NPS flagging is excluded from raw data as requested
    
    # Check if conversation was flagged by each system
    for source_key, details in flagging_details_dict.items():
        # Parse the source to identify the system
        # source_key format is typically: "TABLE_NAME_PROMPT_TYPE"
        source_lower = source_key.lower()
        
        # SA NPS Detection - excluded from raw data as requested
        # Skip SA NPS flagging
        
        # Specialized prompt systems - only set YES if not already NOT_ASSESSED
        if 'false_promises' in source_lower and flagging_columns['FALSE_PROMISES'] != 'NOT_ASSESSED':
            flagging_columns['FALSE_PROMISES'] = 'YES'
        elif 'legal_alignment' in source_lower and flagging_columns['LEGAL_ALIGNMENT'] != 'NOT_ASSESSED':
            flagging_columns['LEGAL_ALIGNMENT'] = 'YES'
        elif 'repetition' in source_lower and flagging_columns['REPETITION'] != 'NOT_ASSESSED':
            flagging_columns['REPETITION'] = 'YES'
        elif 'unresponsive' in source_lower and flagging_columns['UNRESPONSIVE'] != 'NOT_ASSESSED':
            flagging_columns['UNRESPONSIVE'] = 'YES'
        elif ('reported_issues' in source_lower or 'chatcc_reported_issues' in source_lower) and flagging_columns['REPORTED_ISSUES'] != 'NOT_ASSESSED':
            flagging_columns['REPORTED_ISSUES'] = 'YES'
        elif 'interventions' in source_lower and flagging_columns['INTERVENTIONS'] != 'NOT_ASSESSED':
            flagging_columns['INTERVENTIONS'] = 'YES'
        elif 'misprescription' in source_lower and flagging_columns['MISPRESCRIPTION'] != 'NOT_ASSESSED':
            flagging_columns['MISPRESCRIPTION'] = 'YES'
        elif 'unnecessary_clinic' in source_lower and flagging_columns['UNNECESSARY_CLINIC'] != 'NOT_ASSESSED':
            flagging_columns['UNNECESSARY_CLINIC'] = 'YES'
        elif 'clarity_score' in source_lower and flagging_columns['CLARITY_SCORE'] != 'NOT_ASSESSED':
            flagging_columns['CLARITY_SCORE'] = 'YES'
        elif ('wrong_tool' in source_lower or 'wrong_tool_cc_sales_only' in source_lower) and flagging_columns['WRONG_TOOL'] != 'NOT_ASSESSED':
            flagging_columns['WRONG_TOOL'] = 'YES'
        elif ('missed_tool_call' in source_lower or 'missed_tool_cc_sales_only' in source_lower) and flagging_columns['MISSED_TOOL_CALL'] != 'NOT_ASSESSED':
            flagging_columns['MISSED_TOOL_CALL'] = 'YES'
        elif 'unclear_policy' in source_lower and flagging_columns['UNCLEAR_POLICY'] != 'NOT_ASSESSED':
            flagging_columns['UNCLEAR_POLICY'] = 'YES'
        elif 'missing_policy' in source_lower and flagging_columns['MISSING_POLICY'] != 'NOT_ASSESSED':
            flagging_columns['MISSING_POLICY'] = 'YES'
        elif 'wrong_answer' in source_lower and flagging_columns['WRONG_ANSWER'] != 'NOT_ASSESSED':
            flagging_columns['WRONG_ANSWER'] = 'YES'
    
    return flagging_columns

def save_clean_chats_raw_data(session, department_results, target_date):
    """
    Save detailed clean chats results to CLEAN_CHATS_RAW_DATA table with individual flagging columns
    
    Args:
        session: Snowflake session
        department_results: Dictionary of department analysis results
        target_date: Target date for analysis
        
    Returns:
        Success status
    """
    print("💾 Saving clean chats details to database...")
    
    try:
        # Ensure tables exist
        if not create_clean_chats_tables(session):
            return False
        
        # Clear existing data for this date
        cleanup_sql = f"""
        DELETE FROM LLM_EVAL.PUBLIC.CLEAN_CHATS_RAW_DATA 
        WHERE DATE = DATE('{target_date}')
        """
        session.sql(cleanup_sql).collect()
        print(f"    🧹 Cleared existing raw data for {target_date}")
        
        # Insert new detail data - BATCH APPROACH (OPTIMIZED)
        inserted_records = 0
        for department_name, results in department_results.items():
            if results.get('success', False):
                conversation_details = results.get('conversation_details', [])
                
                if not conversation_details:
                    print(f"    ℹ️  No conversation details for {department_name}")
                    continue
                
                print(f"    🚀 Batch inserting {len(conversation_details)} detail records for {department_name}...")
                
                # Process in batches to avoid SQL query length limits
                batch_size = 500  # Process 500 records at a time
                total_batches = (len(conversation_details) + batch_size - 1) // batch_size
                
                for batch_num in range(total_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min(start_idx + batch_size, len(conversation_details))
                    batch_details = conversation_details[start_idx:end_idx]
                    
                    print(f"      📦 Processing batch {batch_num + 1}/{total_batches} ({len(batch_details)} records)...")
                    
                    # Build batch VALUES clause
                    analysis_timestamp = datetime.now()
                    values_clauses = []
                    
                    for detail in batch_details:
                        # Escape single quotes in string fields
                        customer_name = detail['customer_name'].replace("'", "''")
                        agent_names = detail['agent_names'].replace("'", "''")
                        last_skill = detail['last_skill'].replace("'", "''")
                        
                        # Parse flagging details to build individual flagging columns
                        flagging_details_dict = {}
                        if detail.get('flagging_details'):
                            try:
                                flagging_details_dict = json.loads(detail['flagging_details'])
                            except (json.JSONDecodeError, TypeError):
                                flagging_details_dict = {}
                        
                        # Parse assessment error details
                        assessment_error_details_dict = {}
                        if detail.get('assessment_error_details'):
                            try:
                                assessment_error_details_dict = json.loads(detail['assessment_error_details'])
                            except (json.JSONDecodeError, TypeError):
                                assessment_error_details_dict = {}
                        
                        # Get SA flagging information from the detail record
                        sa_nps_flagged = detail.get('sa_nps_flagged', False)
                        specialized_prompt_flagged = detail.get('specialized_prompt_flagged', False)
                        
                        # Build individual flagging column values
                        flagging_columns = build_individual_flagging_columns(
                            department_name, 
                            flagging_details_dict,
                            assessment_error_details_dict,
                            sa_nps_flagged, 
                            specialized_prompt_flagged
                        )
                        
                        values_clause = f"""(
                            DATE('{target_date}'),
                            '{department_name}',
                            '{detail['conversation_id']}',
                            '{customer_name}',
                            '{agent_names}',
                            '{last_skill}',
                            '{detail['is_clean']}',
                            '{flagging_columns['FALSE_PROMISES']}',
                            '{flagging_columns['LEGAL_ALIGNMENT']}',
                            '{flagging_columns['REPETITION']}',
                            '{flagging_columns['UNRESPONSIVE']}',
                            '{flagging_columns['REPORTED_ISSUES']}',
                            '{flagging_columns['INTERVENTIONS']}',
                            '{flagging_columns['MISPRESCRIPTION']}',
                            '{flagging_columns['UNNECESSARY_CLINIC']}',
                            '{flagging_columns['CLARITY_SCORE']}',
                            '{flagging_columns['WRONG_TOOL']}',
                            '{flagging_columns['MISSED_TOOL_CALL']}',
                            '{flagging_columns['UNCLEAR_POLICY']}',
                            '{flagging_columns['MISSING_POLICY']}',
                            '{flagging_columns['WRONG_ANSWER']}',
                            '{analysis_timestamp}'
                        )"""
                        values_clauses.append(values_clause)
                    
                    # Execute batch INSERT
                    batch_insert_sql = f"""
                    INSERT INTO LLM_EVAL.PUBLIC.CLEAN_CHATS_RAW_DATA (
                        DATE,
                        DEPARTMENT,
                        CONVERSATION_ID,
                        CUSTOMER_NAME,
                        AGENT_NAMES,
                        LAST_SKILL,
                        IS_CLEAN,
                        FALSE_PROMISES,
                        LEGAL_ALIGNMENT,
                        REPETITION,
                        UNRESPONSIVE,
                        REPORTED_ISSUES,
                        INTERVENTIONS,
                        MISPRESCRIPTION,
                        UNNECESSARY_CLINIC,
                        CLARITY_SCORE,
                        WRONG_TOOL,
                        MISSED_TOOL_CALL,
                        UNCLEAR_POLICY,
                        MISSING_POLICY,
                        WRONG_ANSWER,
                        ANALYSIS_TIMESTAMP
                    ) VALUES {', '.join(values_clauses)}
                    """
                    
                    session.sql(batch_insert_sql).collect()
                    inserted_records += len(batch_details)
                
                print(f"    ✅ Saved {len(conversation_details)} raw data records for {department_name}")
        
        print(f"    📊 Inserted {inserted_records} total raw data records")
        return True
        
    except Exception as e:
        print(f"    ❌ Error saving clean chats raw data: {str(e)}")
        return False

def save_clean_chats_details(session, department_results, target_date):
    """
    Legacy function name - redirects to save_clean_chats_raw_data for backward compatibility
    """
    return save_clean_chats_raw_data(session, department_results, target_date)

def get_clean_chats_summary_report(session, target_date=None, department_filter=None):
    """
    Generate clean chats summary report from database
    
    Args:
        session: Snowflake session
        target_date: Target date for report (optional)
        department_filter: Specific department filter (optional)
        
    Returns:
        Summary report data
    """
    print("📊 Generating clean chats summary report...")
    
    try:
        # Build query
        where_clauses = []
        
        if target_date:
            where_clauses.append(f"DATE = DATE('{target_date}')")
        
        if department_filter:
            where_clauses.append(f"DEPARTMENT = '{department_filter}'")
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        query = f"""
        SELECT 
            DATE,
            DEPARTMENT,
            TOTAL_CONVERSATIONS,
            CLEAN_CONVERSATIONS,
            FLAGGED_CONVERSATIONS,
            CLEAN_PERCENTAGE,
            FLAGGED_BY_SA_NPS,
            FLAGGED_BY_SPECIALIZED_PROMPTS,
            FLAGGING_BREAKDOWN,
            FALSE_PROMISES_COUNT,
            LEGAL_ALIGNMENT_COUNT,
            REPETITION_COUNT,
            UNRESPONSIVE_COUNT,
            REPORTED_ISSUES_COUNT,
            INTERVENTIONS_COUNT,
            MISPRESCRIPTION_COUNT,
            UNNECESSARY_CLINIC_COUNT,
            CLARITY_SCORE_COUNT,
            WRONG_TOOL_COUNT,
            MISSED_TOOL_CALL_COUNT,
            UNCLEAR_POLICY_COUNT,
            MISSING_POLICY_COUNT,
            WRONG_ANSWER_COUNT,
            ANALYSIS_TIMESTAMP
        FROM LLM_EVAL.PUBLIC.CLEAN_CHATS_SUMMARY
        {where_clause}
        ORDER BY DATE DESC, CLEAN_PERCENTAGE DESC
        """
        
        results = session.sql(query).collect()
        
        if not results:
            print(f"    ℹ️  No clean chats summary data found")
            return []
        
        # Convert to list of dictionaries
        report_data = []
        for row in results:
            report_data.append({
                'date': str(row['DATE']),
                'department': row['DEPARTMENT'],
                'total_conversations': row['TOTAL_CONVERSATIONS'],
                'clean_conversations': row['CLEAN_CONVERSATIONS'],
                'flagged_conversations': row['FLAGGED_CONVERSATIONS'],
                'clean_percentage': row['CLEAN_PERCENTAGE'],
                'flagged_by_sa_nps': row['FLAGGED_BY_SA_NPS'],
                'flagged_by_specialized_prompts': row['FLAGGED_BY_SPECIALIZED_PROMPTS'],
                'flagging_breakdown': json.loads(row['FLAGGING_BREAKDOWN']) if row['FLAGGING_BREAKDOWN'] else {},
                
                # Individual flagging source counts
                'false_promises_count': row['FALSE_PROMISES_COUNT'],
                'legal_alignment_count': row['LEGAL_ALIGNMENT_COUNT'],
                'repetition_count': row['REPETITION_COUNT'],
                'unresponsive_count': row['UNRESPONSIVE_COUNT'],
                'reported_issues_count': row['REPORTED_ISSUES_COUNT'],
                'interventions_count': row['INTERVENTIONS_COUNT'],
                'misprescription_count': row['MISPRESCRIPTION_COUNT'],
                'unnecessary_clinic_count': row['UNNECESSARY_CLINIC_COUNT'],
                'clarity_score_count': row['CLARITY_SCORE_COUNT'],
                'wrong_tool_count': row['WRONG_TOOL_COUNT'],
                'missed_tool_call_count': row['MISSED_TOOL_CALL_COUNT'],
                'unclear_policy_count': row['UNCLEAR_POLICY_COUNT'],
                'missing_policy_count': row['MISSING_POLICY_COUNT'],
                'wrong_answer_count': row['WRONG_ANSWER_COUNT'],
                
                'analysis_timestamp': str(row['ANALYSIS_TIMESTAMP'])
            })
        
        print(f"    ✅ Retrieved {len(report_data)} summary records")
        return report_data
        
    except Exception as e:
        print(f"    ❌ Error generating summary report: {str(e)}")
        return []

def get_clean_chats_detail_report(session, target_date=None, department_filter=None, clean_only=False):
    """
    Generate detailed clean chats report from database
    
    Args:
        session: Snowflake session
        target_date: Target date for report (optional)
        department_filter: Specific department filter (optional)
        clean_only: Return only clean conversations (optional)
        
    Returns:
        Detailed report data
    """
    print("📋 Generating clean chats detail report...")
    
    try:
        # Build query
        where_clauses = []
        
        if target_date:
            where_clauses.append(f"DATE = DATE('{target_date}')")
        
        if department_filter:
            where_clauses.append(f"DEPARTMENT = '{department_filter}'")
        
        if clean_only:
            where_clauses.append("IS_CLEAN = TRUE")
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        query = f"""
        SELECT 
            DATE,
            DEPARTMENT,
            CONVERSATION_ID,
            CUSTOMER_NAME,
            AGENT_NAMES,
            LAST_SKILL,
            IS_CLEAN,
            FALSE_PROMISES,
            LEGAL_ALIGNMENT,
            REPETITION,
            UNRESPONSIVE,
            REPORTED_ISSUES,
            INTERVENTIONS,
            MISPRESCRIPTION,
            UNNECESSARY_CLINIC,
            CLARITY_SCORE,
            WRONG_TOOL,
            MISSED_TOOL_CALL,
            ANALYSIS_TIMESTAMP
        FROM LLM_EVAL.PUBLIC.CLEAN_CHATS_RAW_DATA
        {where_clause}
        ORDER BY DATE DESC, DEPARTMENT, IS_CLEAN DESC, CONVERSATION_ID
        LIMIT 1000  -- Limit for performance
        """
        
        results = session.sql(query).collect()
        
        if not results:
            print(f"    ℹ️  No clean chats detail data found")
            return []
        
        # Convert to list of dictionaries
        report_data = []
        for row in results:
            report_data.append({
                'date': str(row['DATE']),
                'department': row['DEPARTMENT'],
                'conversation_id': row['CONVERSATION_ID'],
                'customer_name': row['CUSTOMER_NAME'],
                'agent_names': row['AGENT_NAMES'],
                'last_skill': row['LAST_SKILL'],
                'is_clean': row['IS_CLEAN'],
                
                # Individual flagging system results
                'false_promises': row['FALSE_PROMISES'],
                'legal_alignment': row['LEGAL_ALIGNMENT'],
                'repetition': row['REPETITION'],
                'unresponsive': row['UNRESPONSIVE'],
                'reported_issues': row['REPORTED_ISSUES'],
                'interventions': row['INTERVENTIONS'],
                'misprescription': row['MISPRESCRIPTION'],
                'unnecessary_clinic': row['UNNECESSARY_CLINIC'],
                'clarity_score': row['CLARITY_SCORE'],
                'wrong_tool': row['WRONG_TOOL'],
                'missed_tool_call': row['MISSED_TOOL_CALL'],
                
                'analysis_timestamp': str(row['ANALYSIS_TIMESTAMP'])
            })
        
        print(f"    ✅ Retrieved {len(report_data)} detail records")
        return report_data
        
    except Exception as e:
        print(f"    ❌ Error generating detail report: {str(e)}")
        return []
