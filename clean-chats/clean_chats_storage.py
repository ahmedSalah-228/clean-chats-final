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
    get_clean_chats_detail_schema
)

def create_clean_chats_tables(session):
    """
    Create clean chats summary and detail tables if they don't exist
    
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
        
        # Create detail table
        detail_schema = get_clean_chats_detail_schema()
        detail_columns = []
        for col_name, col_type in detail_schema.items():
            detail_columns.append(f"{col_name} {col_type}")
        
        detail_table_sql = f"""
        CREATE TABLE IF NOT EXISTS LLM_EVAL.PUBLIC.CLEAN_CHATS_DETAIL (
            {', '.join(detail_columns)}
        )
        """
        
        session.sql(detail_table_sql).collect()
        print("    ✅ CLEAN_CHATS_DETAIL table created/verified")
        
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
                flagging_breakdown_json = json.dumps(results.get('flagging_breakdown', {}))
                analysis_timestamp = datetime.now()
                
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

def save_clean_chats_details(session, department_results, target_date):
    """
    Save detailed clean chats results to CLEAN_CHATS_DETAIL table
    
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
        DELETE FROM LLM_EVAL.PUBLIC.CLEAN_CHATS_DETAIL 
        WHERE DATE = DATE('{target_date}')
        """
        session.sql(cleanup_sql).collect()
        print(f"    🧹 Cleared existing detail data for {target_date}")
        
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
                        flagging_sources = detail['flagging_sources'].replace("'", "''")
                        flagging_details = detail['flagging_details'].replace("'", "''")
                        
                        values_clause = f"""(
                            DATE('{target_date}'),
                            '{department_name}',
                            '{detail['conversation_id']}',
                            '{customer_name}',
                            '{agent_names}',
                            '{last_skill}',
                            {detail['is_clean']},
                            '{flagging_sources}',
                            '{flagging_details}',
                            '{analysis_timestamp}'
                        )"""
                        values_clauses.append(values_clause)
                    
                    # Execute batch INSERT
                    batch_insert_sql = f"""
                    INSERT INTO LLM_EVAL.PUBLIC.CLEAN_CHATS_DETAIL (
                        DATE,
                        DEPARTMENT,
                        CONVERSATION_ID,
                        CUSTOMER_NAME,
                        AGENT_NAMES,
                        LAST_SKILL,
                        IS_CLEAN,
                        FLAGGING_SOURCES,
                        FLAGGING_DETAILS,
                        ANALYSIS_TIMESTAMP
                    ) VALUES {', '.join(values_clauses)}
                    """
                    
                    session.sql(batch_insert_sql).collect()
                    inserted_records += len(batch_details)
                
                print(f"    ✅ Saved {len(conversation_details)} detail records for {department_name}")
        
        print(f"    📊 Inserted {inserted_records} total detail records")
        return True
        
    except Exception as e:
        print(f"    ❌ Error saving clean chats details: {str(e)}")
        return False

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
            FLAGGING_SOURCES,
            FLAGGING_DETAILS,
            ANALYSIS_TIMESTAMP
        FROM LLM_EVAL.PUBLIC.CLEAN_CHATS_DETAIL
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
                'flagging_sources': row['FLAGGING_SOURCES'],
                'flagging_details': json.loads(row['FLAGGING_DETAILS']) if row['FLAGGING_DETAILS'] else {},
                'analysis_timestamp': str(row['ANALYSIS_TIMESTAMP'])
            })
        
        print(f"    ✅ Retrieved {len(report_data)} detail records")
        return report_data
        
    except Exception as e:
        print(f"    ❌ Error generating detail report: {str(e)}")
        return []
