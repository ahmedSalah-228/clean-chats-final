"""
LLM Processing Module for Snowflake Chat Analysis
Handles LLM analysis calls and processing logic
"""

import snowflake.snowpark as snowpark
import pandas as pd
from datetime import datetime
import json
import traceback
from snowflake_llm_config import get_snowflake_llm_departments_config, get_prompt_config, get_metrics_configuration, get_department_summary_schema, get_snowflake_base_departments_config
from snowflake_llm_xml_converter import convert_conversations_to_xml_dataframe, validate_xml_conversion
from LLM_JUDGE.clean_chats_phase2_core_analytics import process_department_phase1, process_department_phase1_multi_day
from snowflake_llm_metrics_calc import *


def get_table_columns(session: snowpark.Session, table_name: str) -> list:
    try:
        cols = session.sql(f"SHOW COLUMNS IN {table_name}").collect()
        return [c['column_name'] for c in cols]
    except Exception:
        return []


def should_use_full_insert(session: snowpark.Session, table_name: str, dynamic_columns: list) -> bool:
    existing_cols = [c.upper() for c in get_table_columns(session, table_name)]
    if not existing_cols:
        # Table not found → full insert (creator will happen in insert_raw_data_with_cleanup)
        return True
    target_cols = [c.upper() for c in dynamic_columns]
    # If exact set match (ignoring order), we can use full insert cleanup (which deletes and reinserts)
    return set(target_cols) == set([c for c in existing_cols if c not in ['DATE', 'DEPARTMENT', 'TIMESTAMP']])


def summary_row_exists(session: snowpark.Session, table_name: str, department: str, target_date: str) -> bool:
    try:
        q = f"SELECT 1 FROM {table_name} WHERE DATE='{target_date}' AND DEPARTMENT='{department}' LIMIT 1"
        return len(session.sql(q).collect()) > 0
    except Exception:
        return False


def insert_raw_data_partial(session: snowpark.Session, table_name: str, department: str, target_date: str, values_dict: dict) -> bool:
    # Ensure table exists; if not, create with full schema from config
    try:
        cols_in_table = get_table_columns(session, table_name)
        if not cols_in_table:
            # Create table with all metric columns from config
            schema_cols = get_department_summary_schema(department)
            create_cols_str = ",\n    ".join([f"{k} {v}" for k, v in schema_cols.items()])
            session.sql(f"CREATE TABLE {table_name} (\n    {create_cols_str}\n)").collect()
            cols_in_table = list(schema_cols.keys())
    except Exception as e:
        print(f"   ❌ Failed ensuring table {table_name}: {str(e)}")
        return False

    # Build lists for numeric vs summary columns
    numeric_cols = []
    summary_cols = []
    for col in cols_in_table:
        if col.upper() in ['DATE', 'DEPARTMENT', 'TIMESTAMP']:
            continue
        # Heuristic: treat columns ending with _ANALYSIS_SUMMARY as summary JSON text columns
        if col.upper().endswith('ANALYSIS_SUMMARY'):
            summary_cols.append(col)
        else:
            numeric_cols.append(col)

    if summary_row_exists(session, table_name, department, target_date):
        # UPDATE only provided columns
        set_parts = ["TIMESTAMP = CURRENT_TIMESTAMP()"]
        for k, v in values_dict.items():
            if k in ['DATE', 'DEPARTMENT', 'TIMESTAMP']:
                continue
            if k not in cols_in_table:
                continue
            if v is None:
                set_parts.append(f"{k} = NULL")
            else:
                # Quote strings; others as-is
                if isinstance(v, str):
                    safe_v = v.replace("'", "''")
                    set_parts.append(f"{k} = '{safe_v}'")
                else:
                    set_parts.append(f"{k} = {v}")
        set_clause = ", ".join(set_parts)
        sql = f"UPDATE {table_name} SET {set_clause} WHERE DATE='{target_date}' AND DEPARTMENT='{department}'"
        session.sql(sql).collect()
        return True
    else:
        # INSERT one row: provided values; all other numeric cols = 0.0; all summary cols = default JSON with zeros
        row = {c: None for c in cols_in_table}
        row['DATE'] = target_date
        row['DEPARTMENT'] = department
        # TIMESTAMP handled by default CURRENT_TIMESTAMP in insert using explicit column
        for k, v in values_dict.items():
            if k in row:
                row[k] = v
        for c in numeric_cols:
            if row.get(c) is None:
                row[c] = 0.0
        for c in summary_cols:
            if row.get(c) is None:
                # default simple JSON with zeros
                row[c] = '{"chats_analyzed": 0, "chats_parsed": 0, "chats_failed": 0, "failure_percentage": 0.0}'

        # Build INSERT
        cols = ['DATE', 'DEPARTMENT', 'TIMESTAMP'] + [c for c in cols_in_table if c not in ['DATE', 'DEPARTMENT', 'TIMESTAMP']]
        values_sql = []
        for c in cols:
            v = row.get(c)
            if c == 'TIMESTAMP':
                values_sql.append('CURRENT_TIMESTAMP()')
            elif v is None:
                values_sql.append('NULL')
            elif isinstance(v, str):
                values_sql.append("'" + v.replace("'", "''") + "'")
            else:
                values_sql.append(str(v))
        sql = f"INSERT INTO {table_name} (" + ", ".join(cols) + ") VALUES (" + ", ".join(values_sql) + ")"
        session.sql(sql).collect()
        return True

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
🚨 LLM ERROR DETAILS {f"- {context}" if context else ""}
{'=' * 50}
Error Type: {type(e).__name__}
Error Message: {str(e)}

Full Traceback:
{error_details}
{'=' * 50}
"""


def run_snowflake_llm_analysis(session: snowpark.Session, xml_content, prompt_config):
    """
    Run LLM analysis using either OpenAI or Gemini based on model_type preference
    
    Args:
        session: Snowflake session
        xml_content: XML formatted conversation content
        prompt_config: Prompt configuration dictionary
    
    Returns:
        LLM response string or None if failed
    """
    try:
        # Escape single quotes in content for SQL
        escaped_content = xml_content.replace("'", "''")
        escaped_prompt = prompt_config['prompt'].replace("'", "''")
        escaped_system = prompt_config['system_prompt'].replace("'", "''")
        
        # Get model configuration
        model_type = prompt_config.get('model_type', 'openai').lower()
        model = prompt_config.get('model', 'gpt-4o-mini')
        temperature = prompt_config.get('temperature', 0.2)
        max_tokens = prompt_config.get('max_tokens', 2048)
        
        # Choose the appropriate LLM function based on model_type
        if model_type == 'openai':
            llm_function = 'openai_chat_system'
        elif model_type == 'gemini':
            llm_function = 'gemini_chat_system'
        else:
            raise ValueError(f"Unsupported model_type: {model_type}")
        
        # Build SQL query with the appropriate function
        sql_query = f"""
        SELECT {llm_function}(
            '{escaped_content}',
            '{escaped_system}',
            '{model}',
            {temperature},
            {max_tokens}
        ) AS llm_response
        """
        
        result = session.sql(sql_query).collect()
        return result[0]['LLM_RESPONSE'] if result else None
        
    except Exception as e:
        print(f"    ⚠️  LLM call failed ({model_type}/{model}): {str(e)}")
        return None


def clean_dataframe_for_snowflake(df):
    """
    Clean DataFrame to ensure Snowflake/PyArrow compatibility.
    
    Args:
        df: Input DataFrame
    
    Returns:
        Cleaned DataFrame with consistent data types
    """
    df_clean = df.copy()
    
    # Convert all object columns to string to avoid mixed type issues
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            # Convert to string and handle NaN
            df_clean[col] = df_clean[col].astype(str).replace('nan', '')
    
    # Ensure datetime columns are properly typed
    datetime_columns = ['ANALYSIS_DATE']
    for col in datetime_columns:
        if col in df_clean.columns:
            try:
                df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')
            except:
                pass
    
    return df_clean


def insert_raw_data_with_cleanup(session: snowpark.Session, table_name: str, department: str, target_date, dataframe: pd.DataFrame, columns: list):
    """
    Dynamically insert raw data into a table with date-based cleanup.
    
    Args:
        session: Snowflake session object
        table_name: Name of the target table
        department: Department value to add to all rows
        dataframe: Pandas dataframe containing the data to insert
        columns: List of column names that should match dataframe columns
        
    Returns:
        dict: Summary of the operation
    """
    
    try:
        # Step 1: Validate dataframe columns match the expected columns
        if len(dataframe.columns) != len(columns):
            raise ValueError(f"Dataframe has {len(dataframe.columns)} columns but expected {len(columns)} columns")
        
        # Step 1: Check if table exists
        try:
            check_query = f"""
            SELECT COUNT(*) AS count
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = UPPER('{table_name}')
            AND TABLE_SCHEMA = CURRENT_SCHEMA()
            """
            exists = session.sql(check_query).collect()[0]['COUNT'] > 0
        except:
            exists = False

        # Step 2: Create table if it doesn't exist
        if not exists:
            essential_cols = {
                'DATE': 'DATE',
                'DEPARTMENT': 'VARCHAR(100)',
                'TIMESTAMP': 'TIMESTAMP'
            }

            # Use VARCHAR as default for dynamic columns (customize if needed)
            dynamic_cols = {col_name: 'VARCHAR(16777216)' for col_name in columns}  # Max VARCHAR length in Snowflake

            full_schema = {**essential_cols, **dynamic_cols}
            create_cols_str = ",\n    ".join([f"{col} {dtype}" for col, dtype in full_schema.items()])
            create_query = f"CREATE TABLE {table_name} (\n    {create_cols_str}\n)"
            session.sql(create_query).collect()
            print(f"✅ Created table {table_name} with {len(full_schema)} columns")
        
        # Step 3: Calculate current timestamp
        current_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"Processing data for date: {target_date}")
        print(f"Target table: {table_name}")
        print(f"Department: {department}")
        print(f"Dataframe shape: {dataframe.shape}")
        
        # Step 4: Remove existing rows for yesterday's date
        delete_query = f"""
        DELETE FROM {table_name} 
        WHERE DATE = '{target_date}' AND DEPARTMENT = '{department}'
        """
        
        delete_result = session.sql(delete_query).collect()
        print(f"Cleaned existing data for {target_date} in department {department}")
        
        # Step 5: Prepare dataframe for insertion
        # Add the essential columns
        dataframe_copy = dataframe.copy()
        dataframe_copy['DATE'] = target_date
        dataframe_copy['TIMESTAMP'] = current_ts
        dataframe_copy['DEPARTMENT'] = department
        
        # Reorder columns to put essential columns first
        essential_cols = ['DATE',  'DEPARTMENT', 'TIMESTAMP']
        dynamic_cols = columns  # The original dynamic columns
        final_column_order = essential_cols + dynamic_cols
        
        # Reorder dataframe columns
        dataframe_copy = dataframe_copy[final_column_order]
        
        # Step 6: Convert pandas dataframe to Snowpark dataframe and write to table
        snowpark_df = session.create_dataframe(dataframe_copy)
        
        # Write to table (append mode)
        snowpark_df.write.mode("append").save_as_table(table_name)
        
        # Step 7: Get final count for verification
        count_query = f"""
        SELECT COUNT(*) as row_count 
        FROM {table_name} 
        WHERE DATE = '{target_date}' AND DEPARTMENT = '{department}'
        """
        
        final_count = session.sql(count_query).collect()[0]['ROW_COUNT']
        
        # Return summary
        summary = {
            "status": "success",
            "table_name": table_name,
            "department": department,
            "date_processed": target_date,
            "timestamp": current_ts,
            "rows_inserted": len(dataframe),
            "final_row_count": final_count,
            "columns_processed": len(columns),
            "total_columns": len(final_column_order)
        }
        
        print(f"Successfully inserted {len(dataframe)} rows into {table_name}")
        print(f"Final count for {target_date}/{department}: {final_count} rows")
        
        return summary
        
    except Exception as e:
        error_summary = {
            "status": "error",
            "table_name": table_name,
            "department": department,
            "error_message": str(e),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"Error processing data: {str(e)}")
        return error_summary


def analyze_conversations_with_prompt(session, conversations_df, department_name, 
                                    prompt_type, prompt_config, target_date):
    """
    Analyze conversations with a specific prompt and save results using batch processing
    
    Args:
        session: Snowflake session
        conversations_df: DataFrame with conversations (XML, segment, or JSON format)
        department_name: Department name
        prompt_type: Type of prompt being used
        prompt_config: Prompt configuration dictionary
        target_date: Target date for analysis
    
    Returns:
        Analysis results dictionary
    """
    model_type = prompt_config.get('model_type', 'openai')
    model = prompt_config.get('model', 'gpt-4o-mini')
    conversion_type = prompt_config.get('conversion_type', 'xml')
    
    # Special handling: per-skill prompts (loss_interest for AT_Filipina)
    if prompt_type == 'loss_interest' and isinstance(prompt_config.get('system_prompt'), dict):
        allowed_skills = list(prompt_config['system_prompt'].keys())
        # Filter incoming conversations by last_skill to only allowed skills
        pre_filter_len = len(conversations_df)
        conversations_df = conversations_df[conversations_df['last_skill'].isin(allowed_skills)].copy() if not conversations_df.empty else conversations_df
        print(f"    🔎 loss_interest per-skill: filtered {pre_filter_len}→{len(conversations_df)} by LAST_SKILL in {allowed_skills}")
    
    print(f"    🔍 Preparing {len(conversations_df)} conversations for batch analysis with {prompt_type} using {model_type}/{model} ({conversion_type} format)...")
    
    if conversations_df.empty:
        print(f"    ⚠️  No conversations to analyze for {prompt_type}")
        return {
            'total_conversations': 0,
            'processed_count': 0,
            'prompt_type': prompt_type,
            'conversion_type': conversion_type,
            'model_type': model_type,
            'model_name': model,
            'success_rate': 0,
            'error': 'No conversations to process'
        }
    
    # Step 1: Prepare all records with empty LLM responses
    llm_results_data = []
    
    
    for _, row in conversations_df.iterrows():
        conversation_content = row.get('conversation_content', '')
        
        result_record = {
            'CONVERSATION_ID': row['conversation_id'],
            'SEGMENT_ID': row.get('segment_id', row['conversation_id']),
            'PROMPT_TYPE': prompt_type,
            'CONVERSION_TYPE': conversion_type,
            'MODEL_TYPE': model_type,
            'MODEL_NAME': model,
            'TEMPERATURE': prompt_config.get('temperature', 0.2),
            'MAX_TOKENS': prompt_config.get('max_tokens', 2048),
            'CONVERSATION_CONTENT': conversation_content,
            'LLM_RESPONSE': '',  # Empty initially - will be filled by batch UPDATE
            'LAST_SKILL': row.get('last_skill', ''),
            'CUSTOMER_NAME': row.get('customer_name', ''),
            'AGENT_NAMES': row.get('agent_names', ''),
            'SEGMENT_INDEX': row.get('segment_index', 0),
            'ANALYSIS_DATE': datetime.now().strftime('%Y-%m-%d'),
            'PROCESSING_STATUS': 'PENDING',  # Will be updated after LLM processing
            'SHADOWED_BY': row.get('shadowed_by', ''),
            'EXECUTION_ID': row.get('execution_id', '')
        }
        llm_results_data.append(result_record)
    
    # Step 2: Batch insert all records with empty LLM responses
    if not llm_results_data:
        print(f"    ⚠️  No data to process for {prompt_type}")
        return {
            'total_conversations': 0,
            'processed_count': 0,
            'prompt_type': prompt_type,
            'conversion_type': conversion_type,
            'model_type': model_type,
            'model_name': model,
            'success_rate': 0,
            'error': 'No data to process'
        }
    
    try:
        # Insert all records to table
        raw_df = pd.DataFrame(llm_results_data)
        raw_df = clean_dataframe_for_snowflake(raw_df)
        
        dynamic_columns = [col for col in raw_df.columns if col not in ['DATE', 'DEPARTMENT', 'TIMESTAMP']]
        
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name=prompt_config['output_table'],
            department=department_name,
            target_date=target_date,
            dataframe=raw_df[dynamic_columns],
            columns=dynamic_columns
        )
        
        if not insert_success:
            print(f"    ❌ Failed to insert records to {prompt_config['output_table']}")
            return {
                'total_conversations': len(conversations_df),
                'processed_count': 0,
                'prompt_type': prompt_type,
                'conversion_type': conversion_type,
                'model_type': model_type,
                'model_name': model,
                'success_rate': 0,
                'error': 'Failed to insert records'
            }
        
        print(f"    💾 Inserted {len(llm_results_data)} records to {prompt_config['output_table']} for batch processing")
        
        # Step 3: Run batch UPDATE query using LLM function
        batch_success, processed_count, failed_count = run_batch_llm_update(
            session, prompt_config, department_name, target_date
        )
        
        if not batch_success:
            print(f"    ❌ Batch LLM update failed for {prompt_type}")
            return {
                'total_conversations': len(conversations_df),
                'processed_count': 0,
                'prompt_type': prompt_type,
                'conversion_type': conversion_type,
                'model_type': model_type,
                'model_name': model,
                'success_rate': 0,
                'error': 'Batch LLM update failed'
            }
        
        success_rate = (processed_count / len(conversations_df) * 100) if len(conversations_df) > 0 else 0
        
        results = {
            'total_conversations': len(conversations_df),
            'processed_count': processed_count,
            'failed_count': failed_count,
            'prompt_type': prompt_type,
            'conversion_type': conversion_type,
            'model_type': model_type,
            'model_name': model,
            'success_rate': success_rate
        }
        
        print(f"    ✅ {prompt_type} batch processing: {processed_count}/{len(conversations_df)} success ({success_rate:.1f}%), {failed_count} failed")
        
        return results
        
    except Exception as e:
        print(f"    ❌ Error in batch processing for {prompt_type}: {str(e)}")
        return {
            'total_conversations': len(conversations_df),
            'processed_count': 0,
            'prompt_type': prompt_type,
            'conversion_type': conversion_type,
            'model_type': model_type,
            'model_name': model,
            'success_rate': 0,
            'error': f'Batch processing error: {str(e)}'
        }


def run_batch_llm_update(session: snowpark.Session, prompt_config, department_name, target_date):
    """
    Run batch UPDATE query to fill LLM responses using Snowflake's LLM functions
    
    Args:
        session: Snowflake session
        prompt_config: Prompt configuration dictionary
        department_name: Department name
        target_date: Target date for analysis
    
    Returns:
        Tuple: (success, processed_count, failed_count)
    """
    import time
    
    # Start total timing
    total_start_time = time.time()
    
    try:
        # Step 1: Setup and validation timing
        setup_start_time = time.time()
        
        table_name = prompt_config['output_table']
        model_type = prompt_config.get('model_type', 'openai').lower()
        departments_config = get_snowflake_base_departments_config()
        gpt_agent_name = departments_config[department_name]['GPT_AGENT_NAME'].replace("'", "''")
        
        # Choose the appropriate LLM function
        if model_type == 'openai':
            llm_function = 'openai_chat_system'
        elif model_type == 'gemini':
            llm_function = 'gemini_chat_system'
        else:
            print(f"    ❌ Unsupported model_type: {model_type}")
            return False, 0, 0
        
        # Use the original prompts - dollar-quoted strings handle all special characters safely
        prompt_text = prompt_config['prompt']
        system_text = prompt_config['system_prompt']
        per_skill_mode = isinstance(system_text, dict)  # loss_interest per LAST_SKILL
        
        setup_time = time.time() - setup_start_time
        print(f"    🔧 Setup completed in {setup_time:.2f}s")
        
        # Step 2: Check pending records count (performance insight)
        count_start_time = time.time()
        
        if per_skill_mode:
            allowed_skills = list(system_text.keys())
            skill_list_sql = ", ".join(["'" + s.replace("'", "''") + "'" for s in allowed_skills])
            count_query = f"""
            SELECT COUNT(*) as pending_count
            FROM {table_name}
            WHERE PROCESSING_STATUS = 'PENDING'
            AND DEPARTMENT = '{department_name}'
            AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
            AND LAST_SKILL IN ({skill_list_sql})
            """
        else:
            count_query = f"""
            SELECT COUNT(*) as pending_count
            FROM {table_name}
            WHERE PROCESSING_STATUS = 'PENDING'
            AND DEPARTMENT = '{department_name}'
            AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
            """
        
        count_result = session.sql(count_query).collect()
        pending_count = count_result[0]['PENDING_COUNT'] if count_result else 0
        
        count_time = time.time() - count_start_time
        print(f"    📊 Found {pending_count} pending records to process (checked in {count_time:.2f}s)")
        
        if pending_count == 0:
            print(f"    ⚠️  No pending records found for {department_name}")
            return True, 0, 0
        
        print(f"    🚀 Running batch {model_type.upper()} analysis on {pending_count} records...")
        
        # Step 3: Build and execute the UPDATE query
        query_build_start_time = time.time()
        
        # BATCH SQL APPROACH (5x faster than UPDATE)
        query_build_time = time.time() - query_build_start_time
        print(f"    📝 Batch SQL approach selected (5x faster)")
        
        execution_start_time = time.time()
        print(f"    ⏳ Starting LLM batch execution... (estimated: {pending_count * 0.4}s+ for {pending_count} records)")
        
        try:
            # Step 1: Check if system prompt contains @Prompt@ placeholder
            needs_prompt_replacement = '@Prompt@' in (system_text if not per_skill_mode else "".join(system_text.values()))
            
            if needs_prompt_replacement or per_skill_mode:
                print(f"    🔄 System prompt contains @Prompt@ - fetching conversation-specific prompts...")
                
                # Create batch processing query with dynamic system prompt replacement
                if per_skill_mode:
                    # Build CASE expression selecting prompt by LAST_SKILL
                    departments_config_full = get_snowflake_llm_departments_config()
                    # allowed skills based on keys
                    allowed_skills = list(system_text.keys())
                    skill_list_sql = ", ".join(["'" + s.replace("'", "''") + "'" for s in allowed_skills])

                    case_branches = []
                    for skill, prompt in system_text.items():
                        safe_skill = skill.replace("'", "''")
                        safe_prompt = prompt  # will be dollar-quoted
                        case_branches.append(f"WHEN LAST_SKILL = '{safe_skill}' THEN $${safe_prompt}$$")
                    case_expr = "CASE " + " ".join(case_branches) + " END"

                    batch_query = f"""
                    WITH batch_processing AS (
                        SELECT 
                            CONVERSATION_ID,
                            {llm_function}(
                                CONVERSATION_CONTENT,
                                REPLACE(
                                    REPLACE({case_expr}, '@Prompt@', COALESCE(GET_N8N_SYSTEM_PROMPT(EXECUTION_ID), GET_ERP_SYSTEM_PROMPT(CONVERSATION_ID), '@Prompt@')),
                                    '<STEP-NAME>', COALESCE(LAST_SKILL, '<STEP-NAME>')
                                ),
                                MODEL_NAME,
                                TEMPERATURE,
                                MAX_TOKENS
                            ) AS llm_response
                        FROM {table_name}
                        WHERE PROCESSING_STATUS = 'PENDING'
                        AND DEPARTMENT = '{department_name}'
                        AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
                        AND LAST_SKILL IN ({skill_list_sql})
                    )
                    SELECT CONVERSATION_ID, llm_response FROM batch_processing
                    """
                else:
                    batch_query = f"""
                WITH batch_processing AS (
                    SELECT 
                        CONVERSATION_ID,
                        {llm_function}(
                            CONVERSATION_CONTENT,
                            REPLACE(
                                REPLACE($${system_text}$$, '@Prompt@', COALESCE(GET_N8N_SYSTEM_PROMPT(EXECUTION_ID), GET_ERP_SYSTEM_PROMPT(CONVERSATION_ID), '@Prompt@')),
                                '<STEP-NAME>', COALESCE(LAST_SKILL, '<STEP-NAME>')
                            ),
                            MODEL_NAME,
                            TEMPERATURE,
                            MAX_TOKENS
                        ) AS llm_response
                    FROM {table_name}
                    WHERE PROCESSING_STATUS = 'PENDING'
                    AND DEPARTMENT = '{department_name}'
                    AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
                )
                SELECT CONVERSATION_ID, llm_response FROM batch_processing
                """
            else:
                # Original batch processing without prompt replacement
                if per_skill_mode:
                    allowed_skills = list(system_text.keys())
                    skill_list_sql = ", ".join(["'" + s.replace("'", "''") + "'" for s in allowed_skills])
                    case_branches = []
                    for skill, prompt in system_text.items():
                        safe_skill = skill.replace("'", "''")
                        safe_prompt = prompt
                        case_branches.append(f"WHEN LAST_SKILL = '{safe_skill}' THEN $${safe_prompt}$$")
                    case_expr = "CASE " + " ".join(case_branches) + " END"
                    batch_query = f"""
                    WITH batch_processing AS (
                        SELECT 
                            CONVERSATION_ID,
                            {llm_function}(
                                CONVERSATION_CONTENT,
                                {case_expr},
                                MODEL_NAME,
                                TEMPERATURE,
                                MAX_TOKENS
                            ) AS llm_response
                        FROM {table_name}
                        WHERE PROCESSING_STATUS = 'PENDING'
                        AND DEPARTMENT = '{department_name}'
                        AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
                        AND LAST_SKILL IN ({skill_list_sql})
                    )
                    SELECT CONVERSATION_ID, llm_response FROM batch_processing
                    """
                else:
                    batch_query = f"""
                WITH batch_processing AS (
                    SELECT 
                        CONVERSATION_ID,
                        {llm_function}(
                            CONVERSATION_CONTENT,
                            $${system_text}$$,
                            MODEL_NAME,
                            TEMPERATURE,
                            MAX_TOKENS
                        ) AS llm_response
                    FROM {table_name}
                    WHERE PROCESSING_STATUS = 'PENDING'
                    AND DEPARTMENT = '{department_name}'
                    AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
                )
                SELECT CONVERSATION_ID, llm_response FROM batch_processing
                """
            
            # Execute batch processing
            batch_results = session.sql(batch_query).collect()
        
            if not batch_results:
                print(f"    ⚠️  No results from batch processing")
                execution_time = time.time() - execution_start_time
            else:
                # Step 2: Update original table with batch results
                print(f"    🔄 Updating {len(batch_results)} records with LLM responses...")
                
                # Create temp table with results for efficient UPDATE
                temp_results_table = f"TEMP_BATCH_RESULTS_{int(time.time())}"
                
                # Convert results to DataFrame
                results_data = [{'CONVERSATION_ID': row['CONVERSATION_ID'], 'LLM_RESPONSE': row['LLM_RESPONSE']} for row in batch_results]
                results_df = session.create_dataframe(results_data)
                results_df.write.mode("overwrite").save_as_table(temp_results_table)
                
                # Update original table using JOIN on CONVERSATION_ID
                update_query = f"""
                UPDATE {table_name}
                SET 
                    LLM_RESPONSE = temp.LLM_RESPONSE,
                    PROCESSING_STATUS = 'COMPLETED'
                FROM {temp_results_table} temp
                WHERE {table_name}.CONVERSATION_ID = temp.CONVERSATION_ID
                """
                
                session.sql(update_query).collect()
                
                # Clean up temp table
                session.sql(f"DROP TABLE {temp_results_table}").collect()
                
                execution_time = time.time() - execution_start_time
                print(f"    ✅ Batch SQL approach completed successfully")
                
        except Exception as batch_error:
            print(f"    ⚠️  Batch SQL failed, falling back to UPDATE method: {str(batch_error)}")
            
            # Fallback to original UPDATE method with prompt replacement support
            if needs_prompt_replacement or per_skill_mode:
                print(f"    🔄 Using UPDATE method with @Prompt@ replacement...")
                if per_skill_mode:
                    allowed_skills = list(system_text.keys())
                    skill_list_sql = ", ".join(["'" + s.replace("'", "''") + "'" for s in allowed_skills])
                    case_branches = []
                    for skill, prompt in system_text.items():
                        safe_skill = skill.replace("'", "''")
                        safe_prompt = prompt
                        case_branches.append(
                            f"WHEN LAST_SKILL = '{safe_skill}' THEN REPLACE($${safe_prompt}$$, '@Prompt@', COALESCE(GET_N8N_SYSTEM_PROMPT({table_name}.EXECUTION_ID), '@Prompt@'))"
                        )
                    case_expr = "CASE " + " ".join(case_branches) + " END"
                    update_query = f"""
                    UPDATE {table_name}
                    SET 
                        LLM_RESPONSE = {llm_function}(
                                        CONVERSATION_CONTENT,
                                        REPLACE({case_expr}, '<STEP-NAME>', COALESCE({table_name}.LAST_SKILL, '<STEP-NAME>')),
                                        MODEL_NAME,
                                        TEMPERATURE,
                                        MAX_TOKENS
                                    ),
                                    PROCESSING_STATUS = 'COMPLETED'
                                WHERE PROCESSING_STATUS = 'PENDING'
                                AND DEPARTMENT = '{department_name}'
                                AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
                                AND LAST_SKILL IN ({skill_list_sql})
                                """
                else:
                    update_query = f"""
                    UPDATE {table_name}
                    SET 
                        LLM_RESPONSE = {llm_function}(
                                CONVERSATION_CONTENT,
                                REPLACE(
                                    REPLACE($${system_text}$$, '@Prompt@', COALESCE(GET_N8N_SYSTEM_PROMPT({table_name}.EXECUTION_ID), GET_ERP_SYSTEM_PROMPT({table_name}.CONVERSATION_ID), '@Prompt@')),
                                    '<STEP-NAME>', COALESCE({table_name}.LAST_SKILL, '<STEP-NAME>')
                                ),
                            MODEL_NAME,
                            TEMPERATURE,
                            MAX_TOKENS
                        ),
                        PROCESSING_STATUS = 'COMPLETED'
                    WHERE PROCESSING_STATUS = 'PENDING'
                    AND DEPARTMENT = '{department_name}'
                    AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
                    """
            else:
                # Original UPDATE method without prompt replacement
                update_query = f"""
                UPDATE {table_name}
                SET 
                    LLM_RESPONSE = {llm_function}(
                        CONVERSATION_CONTENT,
                        $${system_text}$$,
                MODEL_NAME,
                TEMPERATURE,
                MAX_TOKENS
            ),
            PROCESSING_STATUS = 'COMPLETED'
        WHERE PROCESSING_STATUS = 'PENDING'
        AND DEPARTMENT = '{department_name}'
        AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
        """
        
        result = session.sql(update_query).collect()
        execution_time = time.time() - execution_start_time
        print(f"    ✅ Fallback UPDATE method completed")
        records_per_second = pending_count / execution_time if execution_time > 0 else 0
        
        print(f"    ✅ Batch UPDATE executed in {execution_time:.2f}s")
        print(f"    📈 Performance: {records_per_second:.2f} records/second")
        print(f"    🔍 Average time per record: {execution_time/pending_count:.2f}s" if pending_count > 0 else "")
        
        # Step 4: Count successes and failures with timing
        counting_start_time = time.time()
        
        # Narrow counting for per-skill mode to the allowed skill subset
        if per_skill_mode:
            allowed_skills = list(system_text.keys())
            skill_list_sql = ", ".join(["'" + s.replace("'", "''") + "'" for s in allowed_skills])
            processed_count, failed_count = count_llm_results_with_extra_filter(
                session, table_name, department_name, target_date, f"AND LAST_SKILL IN ({skill_list_sql})"
            )
        else:
            processed_count, failed_count = count_llm_results(session, table_name, department_name, target_date)
        
        counting_time = time.time() - counting_start_time
        print(f"    📊 Results counted in {counting_time:.2f}s")
        
        # Total timing summary
        total_time = time.time() - total_start_time
        print(f"    🏁 TOTAL BATCH TIME: {total_time:.2f}s for {pending_count} records")
        print(f"    📋 Time breakdown:")
        print(f"       - Setup: {setup_time:.2f}s ({setup_time/total_time*100:.1f}%)")
        print(f"       - Counting: {count_time:.2f}s ({count_time/total_time*100:.1f}%)")
        print(f"       - Query Build: {query_build_time:.3f}s ({query_build_time/total_time*100:.1f}%)")
        print(f"       - LLM Execution: {execution_time:.2f}s ({execution_time/total_time*100:.1f}%)")
        print(f"       - Results: {counting_time:.2f}s ({counting_time/total_time*100:.1f}%)")
        
        # Performance insights
        if execution_time > 30:
            print(f"    ⚠️  SLOW EXECUTION DETECTED!")
            print(f"       - Consider reducing batch size or checking Snowflake compute resources")
            print(f"       - {model_type.upper()} may be rate-limited or overloaded")
        
        if records_per_second < 0.5:
            print(f"    🐌 LOW THROUGHPUT WARNING: {records_per_second:.2f} records/second")
            print(f"       - Expected: 1-5 records/second for typical LLM operations")
        
        return True, processed_count, failed_count
        
    except Exception as e:
        total_time = time.time() - total_start_time
        error_details = format_error_details(e, f"BATCH LLM UPDATE - {department_name}")
        print(f"    ❌ Batch LLM update failed after {total_time:.2f}s: {str(e)}")
        print(error_details)
        return False, 0, 0


def count_llm_results(session: snowpark.Session, table_name, department_name, target_date):
    """
    Count successful and failed LLM responses by checking for error patterns
    
    Args:
        session: Snowflake session
        table_name: Full table name
        department_name: Department name
        target_date: Target date
    
    Returns:
        Tuple: (processed_count, failed_count)
    """
    import time
    
    try:
        # Count total completed records with timing
        total_start_time = time.time()
        
        total_query = f"""
        SELECT COUNT(*) as total_count
        FROM {table_name}
        WHERE PROCESSING_STATUS = 'COMPLETED'
        AND DEPARTMENT = '{department_name}'
        AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
        """
        
        total_result = session.sql(total_query).collect()
        total_count = total_result[0]['TOTAL_COUNT'] if total_result else 0
        
        total_time = time.time() - total_start_time
        
        # Count failed records (those with error patterns) with timing
        failed_start_time = time.time()
        
        failed_query = f"""
        SELECT COUNT(*) as failed_count
        FROM {table_name}
        WHERE PROCESSING_STATUS = 'COMPLETED'
        AND DEPARTMENT = '{department_name}'
        AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
        AND (
            LLM_RESPONSE LIKE '%[gemini_chat error]%'
            OR LLM_RESPONSE LIKE '%[openai_chat error]%'
            OR LLM_RESPONSE IS NULL
            OR LLM_RESPONSE = ''
        )
        """
        
        failed_result = session.sql(failed_query).collect()
        failed_count = failed_result[0]['FAILED_COUNT'] if failed_result else 0
        
        failed_time = time.time() - failed_start_time
        
        processed_count = total_count - failed_count
        success_rate = (processed_count / total_count * 100) if total_count > 0 else 0
        
        print(f"    📊 Results: {processed_count} successful, {failed_count} failed out of {total_count} total ({success_rate:.1f}% success)")
        print(f"    ⏱️  Counting times: Total query {total_time:.2f}s, Failed query {failed_time:.2f}s")
        
        # Quality insights
        if success_rate < 90 and total_count > 0:
            print(f"    ⚠️  LOW SUCCESS RATE: {success_rate:.1f}% - Check LLM function issues")
        
        if total_time > 2 or failed_time > 2:
            print(f"    🐌 SLOW COUNTING: Consider adding indexes on PROCESSING_STATUS, DEPARTMENT, DATE")
        
        return processed_count, failed_count
        
    except Exception as e:
        print(f"    ⚠️  Error counting results: {str(e)}")
        return 0, 0


def count_llm_results_with_extra_filter(session: snowpark.Session, table_name, department_name, target_date, extra_where_clause):
    """
    Variant of count_llm_results that accepts an additional WHERE clause snippet
    to narrow counting (e.g., by LAST_SKILL for per-skill prompts).
    """
    import time
    try:
        total_start_time = time.time()
        total_query = f"""
        SELECT COUNT(*) as total_count
        FROM {table_name}
        WHERE PROCESSING_STATUS = 'COMPLETED'
        AND DEPARTMENT = '{department_name}'
        AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
        {extra_where_clause}
        """
        total_result = session.sql(total_query).collect()
        total_count = total_result[0]['TOTAL_COUNT'] if total_result else 0

        failed_start_time = time.time()
        failed_query = f"""
        SELECT COUNT(*) as failed_count
        FROM {table_name}
        WHERE PROCESSING_STATUS = 'COMPLETED'
        AND DEPARTMENT = '{department_name}'
        AND DATE = '{target_date if target_date else datetime.now().strftime("%Y-%m-%d")}'
        {extra_where_clause}
        AND (
            LLM_RESPONSE LIKE '%[gemini_chat error]%'
            OR LLM_RESPONSE LIKE '%[openai_chat error]%'
            OR LLM_RESPONSE IS NULL
            OR LLM_RESPONSE = ''
        )
        """
        failed_result = session.sql(failed_query).collect()
        failed_count = failed_result[0]['FAILED_COUNT'] if failed_result else 0

        processed_count = total_count - failed_count
        return processed_count, failed_count
    except Exception as e:
        print(f"    ⚠️  Error counting results (filtered): {str(e)}")
        return 0, 0


def process_department_llm_analysis(session: snowpark.Session, department_name, target_date=None, selected_prompts=None):
    """
    Process LLM analysis for a single department - follows the same pattern as existing code
    
    Args:
        session: Snowflake session
        department_name: Department name to process
        target_date: Target date for analysis
    
    Returns:
        Tuple: (department_results, success)
    """
    print(f"\n🤖 PROCESSING LLM ANALYSIS: {department_name}")
    print("=" * 50)
    
    try:
        # Step 1: Get filtered data using existing Phase 1 foundation
        print(f"📊 Step 1: Loading filtered data...")
        filtered_df, phase1_stats, success = process_department_phase1(
            session, department_name, target_date
        )
        
        if not success or filtered_df.empty:
            print(f"    ❌ No filtered data from Phase 1")
            return {'error': 'No filtered data from Phase 1'}, False
        
        print(f"    ✅ Loaded {len(filtered_df)} rows, {filtered_df['CONVERSATION_ID'].nunique()} conversations")
        
        # Step 2: Get department configuration for prompt processing
        departments_config = get_snowflake_llm_departments_config()
        dept_config = departments_config[department_name]
        
        if 'llm_prompts' not in dept_config or not dept_config['llm_prompts']:
            print(f"    ⚠️  No LLM prompts configured for {department_name}")
            return {'error': 'No LLM prompts configured'}, False
        
        # Step 3: Process each prompt type with appropriate conversion
        department_results = {}
        
        # Filter prompts if a subset was requested
        all_prompts = dept_config['llm_prompts']
        if selected_prompts is None or selected_prompts == ['*']:
            prompts_to_run = all_prompts
        else:
            selected_set = set(selected_prompts)
            prompts_to_run = {k: v for k, v in all_prompts.items() if (k in selected_set)}
            missing = [p for p in selected_prompts if p not in all_prompts]
            if missing:
                print(f"    ⚠️  Skipping unknown prompts for {department_name}: {missing}")

        for prompt_type, prompt_config in prompts_to_run.items():
            print(f"  🎯 Processing prompt: {prompt_type}")
            
            # Step 2a: Choose conversion method based on prompt config
            conversion_type = prompt_config.get('conversion_type', 'xml')  # Default to XML
            
            if prompt_type == 'misprescription':
                print(f"    🔄 Filtering for misprescription...")
                filtered_df_2 = filter_conversations_by_category(session, filtered_df, 'OTC Medication Advice', department_name, target_date)
            elif prompt_type == 'unnecessary_clinic' or prompt_type == 'clinic_recommendation_reason':
                print(f"    🔄 Filtering for unnecessary clinic...")
                filtered_df_2 = filter_conversations_by_category(session, filtered_df, 'Clinic Recommendation', department_name, target_date)
            else:
                filtered_df_2 = filtered_df
            
            if conversion_type == 'xml':
                print(f"    🔄 Converting to XML format for {prompt_type}...")
                from snowflake_llm_xml_converter import convert_conversations_to_xml_dataframe, validate_xml_conversion
                
                conversations_df = convert_conversations_to_xml_dataframe(filtered_df_2, department_name)
                if conversations_df.empty:
                    print(f"    ❌ No conversations converted to XML for {prompt_type}")
                    department_results[prompt_type] = {'error': 'No XML conversations', 'conversion_type': 'xml'}
                    continue
                
                # Validate conversion
                validation_results = validate_xml_conversion(conversations_df, department_name)
                print(f"    ✅ XML conversion: {validation_results['valid_xml_count']}/{validation_results['total_conversations']} valid ({validation_results['success_rate']:.1f}%)")
                
                # Rename column for consistency
                conversations_df['conversation_content'] = conversations_df['content_xml_view']
                
            elif conversion_type == 'segment':
                print(f"    🔄 Converting to segment format for {prompt_type}...")
                from snowflake_llm_segment_converter import convert_conversations_to_segment_dataframe, validate_segment_conversion
                
                conversations_df = convert_conversations_to_segment_dataframe(filtered_df_2, department_name)
                if conversations_df.empty:
                    print(f"    ❌ No conversations converted to segment for {prompt_type}")
                    department_results[prompt_type] = {'error': 'No segment conversations', 'conversion_type': 'segment'}
                    continue
                
                # Validate conversion
                validation_results = validate_segment_conversion(conversations_df, department_name)
                print(f"    ✅ Segment conversion: {validation_results['valid_segment_count']}/{validation_results['total_bot_segments']} valid BOT segments ({validation_results['success_rate']:.1f}%) from {validation_results['unique_conversations']} conversations")
                
                # Rename column for consistency
                conversations_df['conversation_content'] = conversations_df['messages']
                
            elif conversion_type == 'json':
                print(f"    🔄 Converting to JSON format for {prompt_type}...")
                from snowflake_llm_json_converter import convert_conversations_to_json_dataframe, validate_json_conversion
                
                conversations_df = convert_conversations_to_json_dataframe(filtered_df_2, department_name)
                if conversations_df.empty:
                    print(f"    ❌ No conversations converted to JSON for {prompt_type}")
                    department_results[prompt_type] = {'error': 'No JSON conversations', 'conversion_type': 'json'}
                    continue
                
                # Validate conversion
                validation_results = validate_json_conversion(conversations_df, department_name)
                print(f"    ✅ JSON conversion: {validation_results['valid_json_count']}/{validation_results['total_conversations']} valid JSON conversations ({validation_results['success_rate']:.1f}%)")
                
                # Rename column for consistency
                conversations_df['conversation_content'] = conversations_df['content_json_view']
                
                # If this is the loss_interest prompt with per-skill system prompts, pre-filter rows
                if prompt_type == 'loss_interest' and isinstance(prompt_config.get('system_prompt'), dict):
                    allowed_skills = list(prompt_config['system_prompt'].keys())
                    before_len = len(conversations_df)
                    conversations_df = conversations_df[conversations_df['last_skill'].isin(allowed_skills)].copy()
                    print(f"    🎛️ loss_interest: filtered JSON conversations {before_len}→{len(conversations_df)} by LAST_SKILL")
                
            elif conversion_type == 'xml3d':
                print(f"    🔄 Converting to XML3D format for {prompt_type}...")
                from snowflake_llm_xml3d import convert_conversations_to_xml3d, validate_xml3d_conversion

                filtered_df_3d, phase1_stats_3d, success = process_department_phase1_multi_day(
                    session, department_name, target_date
                )
                
                conversations_df = convert_conversations_to_xml3d(filtered_df_3d, department_name)
                if conversations_df.empty:
                    print(f"    ❌ No conversations converted to XML3D for {prompt_type}")
                    department_results[prompt_type] = {'error': 'No XML3D conversations', 'conversion_type': 'xml3d'}
                    continue
                
                # Validate conversion
                validation_results = validate_xml3d_conversion(conversations_df, department_name)
                print(f"    ✅ XML3D conversion: {validation_results['valid_xml3d_count']}/{validation_results['total_conversations']} valid XML3D conversations ({validation_results['success_rate']:.1f}%)")
                
                # Rename column for consistency
                conversations_df['conversation_content'] = conversations_df['content_xml_view']
                
            else:
                print(f"    ❌ Unknown conversion type: {conversion_type}")
                department_results[prompt_type] = {'error': f'Unknown conversion type: {conversion_type}'}
                continue
            
            # Process conversations with this prompt
            prompt_results = analyze_conversations_with_prompt(
                session, conversations_df, department_name, prompt_type, 
                prompt_config, target_date
            )
            
            department_results[prompt_type] = prompt_results
        
        # Calculate overall department statistics
        total_prompts = len(department_results)
        successful_prompts = sum(1 for result in department_results.values() 
                               if result.get('processed_count', 0) > 0)
        total_conversations = sum(result.get('total_conversations', 0) for result in department_results.values() 
                                if isinstance(result, dict))
        
        print(f"\n✅ {department_name} COMPLETED:")
        print(f"   🎯 Prompts processed: {successful_prompts}/{total_prompts}")
        print(f"   💬 Conversations analyzed: {total_conversations}")
        
        return department_results, True
        
    except Exception as e:
        error_msg = f"LLM analysis failed: {str(e)}"
        error_details = format_error_details(e, f"DEPARTMENT LLM ANALYSIS - {department_name}")
        print(f"  ❌ {department_name}: {error_msg}")
        print(error_details)
        return {'error': error_msg, 'traceback': str(e)}, False


def update_department_master_summary(session: snowpark.Session, department_name, target_date, selected_metrics=None):
    """
    Calculate metrics and update department-specific master summary table
    
    Args:
        session: Snowflake session
        department_name: Department name to process
        target_date: Target date for analysis
    
    Returns:
        Success status and summary of metrics calculated
    """
    print(f"📊 UPDATING DEPARTMENT MASTER SUMMARY: {department_name}")
    
    try:
        # Get department's metrics configuration
        metrics_config = get_metrics_configuration()
        
        if department_name not in metrics_config:
            print(f"   ⚠️  No metrics configuration found for {department_name}")
            return True, {'warning': f'No metrics configuration for {department_name}'}
        
        dept_config = metrics_config[department_name]
        master_table = dept_config['master_table']
        dept_metrics = dept_config['metrics']
        # Filter metrics if a subset was requested
        if selected_metrics is not None and selected_metrics != ['*']:
            selected_set = set(selected_metrics)
            missing_metrics = [m for m in selected_metrics if m not in dept_metrics]
            if missing_metrics:
                print(f"   ⚠️  Skipping unknown metrics for {department_name}: {missing_metrics}")
            dept_metrics = {k: v for k, v in dept_metrics.items() if k in selected_set}
        
        print(f"   🎯 Processing {len(dept_metrics)} metrics for {department_name}")
        
        # Get department's configured prompts to check dependencies
        departments_config = get_snowflake_llm_departments_config()
        configured_prompts = list(departments_config.get(department_name, {}).get('llm_prompts', {}).keys())
        
        # Calculate metrics in order
        metric_results = {}
        successful_metrics = 0
        failed_metrics = 0
        
        for metric_name, metric_config in sorted(dept_metrics.items(), key=lambda x: x[1]['order']):
            print(f"   📈 Calculating {metric_name}...")
            
            # Check if required prompts are configured for this department
            required_prompts = metric_config['depends_on_prompts']
            missing_prompts = [p for p in required_prompts if p not in configured_prompts]
            
            if missing_prompts:
                print(f"     ⚠️  Missing required prompts {missing_prompts} - setting NULL")
                # Set NULL values for missing dependencies
                for col in metric_config['columns']:
                    metric_results[col] = None
                failed_metrics += 1
                continue
            
            try:
                # Get the function object directly from configuration
                calc_function = metric_config['function']
                
                # Validate that it's actually a callable function
                if not callable(calc_function):
                    print(f"     ❌ Function {calc_function} is not callable")
                    # Set NULL values for invalid function
                    for col in metric_config['columns']:
                        metric_results[col] = None
                    failed_metrics += 1
                    continue
                
                # Call the function (all functions take session and target_date)
                result = calc_function(session, department_name, target_date)
                
                # Map results to column names
                columns = metric_config['columns']
                if isinstance(result, tuple):
                    # Multiple return values
                    for i, col in enumerate(columns):
                        metric_results[col] = result[i] if i < len(result) else None
                elif isinstance(result, dict):
                    # Dictionary return (for weighted NPS)
                    if len(columns) == 1 and department_name in result:
                        metric_results[columns[0]] = result[department_name]
                    else:
                        # Set NULL if department not found in result
                        for col in columns:
                            metric_results[col] = None
                else:
                    # Single return value
                    if len(columns) == 1:
                        metric_results[columns[0]] = result
                    else:
                        print(f"     ⚠️  Mismatch: function returned single value but {len(columns)} columns expected")
                        metric_results[columns[0]] = result
                        for col in columns[1:]:
                            metric_results[col] = None
                
                successful_metrics += 1
                print(f"     ✅ {metric_name} calculated successfully")
                
            except Exception as e:
                print(f"     ❌ Error calculating {metric_name}: {str(e)}")
                # Set NULL values for failed calculation
                for col in metric_config['columns']:
                    metric_results[col] = None
                failed_metrics += 1
                continue
        
        # Prepare record for insertion
        summary_record = {
            **metric_results,  # All calculated metrics
        }
        
        # Convert to DataFrame
        summary_df = pd.DataFrame([summary_record])
        summary_df = clean_dataframe_for_snowflake(summary_df)
        
        # Get dynamic columns (excluding DATE, DEPARTMENT, TIMESTAMP)
        dynamic_columns = [col for col in summary_df.columns if col not in ['DATE', 'DEPARTMENT', 'TIMESTAMP']]
        
        # Decide full insert vs partial upsert
        if should_use_full_insert(session, master_table, dynamic_columns):
            # Insert using existing pattern
            insert_success = insert_raw_data_with_cleanup(
                session=session,
                table_name=master_table,
                department=department_name,
                target_date=target_date,
                dataframe=summary_df[dynamic_columns],
                columns=dynamic_columns
            )
        else:
            # Partial update/insert
            insert_success = insert_raw_data_partial(
                session=session,
                table_name=master_table,
                department=department_name,
                target_date=target_date,
                values_dict=summary_df.iloc[0].to_dict()
            )
        
        if insert_success:
            print(f"   ✅ Updated {master_table}: {successful_metrics} metrics calculated, {failed_metrics} set to NULL")
            
            summary = {
                'master_table': master_table,
                'total_metrics': len(dept_metrics),
                'successful_metrics': successful_metrics,
                'failed_metrics': failed_metrics,
                'metric_results': metric_results
            }
            return True, summary
        else:
            print(f"   ❌ Failed to insert into {master_table}")
            return False, {'error': f'Failed to insert into {master_table}'}
        
    except Exception as e:
        error_details = format_error_details(e, f"DEPARTMENT MASTER SUMMARY - {department_name}")
        print(f"   ❌ Failed to update department master summary: {str(e)}")
        print(error_details)
        return False, {'error': str(e)}


def update_llm_master_summary(session: snowpark.Session, department_results, target_date, selected_metrics=None):
    """
    Update department-specific master summary tables with calculated metrics
    
    Args:
        session: Snowflake session
        department_results: Dictionary with results for each department
        target_date: Target date for analysis
    
    Returns:
        Success status
    """
    print(f"\n📊 UPDATING DEPARTMENT MASTER SUMMARIES...")
    
    try:
        summary_stats = {
            'total_departments': 0,
            'successful_departments': 0,
            'failed_departments': 0,
            'total_metrics_calculated': 0,
            'total_metrics_failed': 0
        }
        
        # Process each department that had LLM analysis
        for department_name, dept_results in department_results.items():
            if 'error' in dept_results:
                print(f"   ⚠️  Skipping {department_name} - LLM analysis failed: {dept_results['error']}")
                summary_stats['failed_departments'] += 1
                continue
            
            summary_stats['total_departments'] += 1
            
            # Update this department's master summary table
            # selected_metrics is passed via orchestrator for single-department runs; for multi dept keep full
            success, dept_summary = update_department_master_summary(session, department_name, target_date, selected_metrics)
            
            if success:
                summary_stats['successful_departments'] += 1
                if isinstance(dept_summary, dict):
                    summary_stats['total_metrics_calculated'] += dept_summary.get('successful_metrics', 0)
                    summary_stats['total_metrics_failed'] += dept_summary.get('failed_metrics', 0)
                    print(f"   ✅ {department_name}: {dept_summary.get('successful_metrics', 0)} metrics calculated")
            else:
                summary_stats['failed_departments'] += 1
                print(f"   ❌ {department_name}: Failed to update master summary")
        
        # Print overall summary
        print(f"\n📊 MASTER SUMMARY UPDATE COMPLETED:")
        print(f"   🏢 Departments processed: {summary_stats['successful_departments']}/{summary_stats['total_departments']}")
        print(f"   📈 Total metrics calculated: {summary_stats['total_metrics_calculated']}")
        print(f"   ⚠️  Total metrics set to NULL: {summary_stats['total_metrics_failed']}")
        
        if summary_stats['failed_departments'] > 0:
            print(f"   ❌ Failed departments: {summary_stats['failed_departments']}")
        
        return summary_stats['failed_departments'] == 0
        
    except Exception as e:
        error_details = format_error_details(e, "UPDATE DEPARTMENT MASTER SUMMARIES")
        print(f"   ❌ Failed to update master summaries: {str(e)}")
        print(error_details)
        return False


def filter_conversations_by_category(session: snowpark.Session, filtered_df, category_name, department_name, target_date):
    """
    Filter conversations based on categorizing data from DOCTORS_CATEGORIZING_RAW_DATA table
    
    Args:
        session: Snowflake session
        filtered_df: DataFrame with conversations to filter
        category_name: Category name to filter by (e.g., "Insurance Inquiries", "Emergency Medical", etc.)
        department_name: Department name for filtering
        target_date: Target date for filtering
    
    Returns:
        Filtered DataFrame containing only conversations that match the specified category
    """
    print(f"🔍 FILTERING CONVERSATIONS BY CATEGORY: {category_name}")
    print(f"   📊 Input DataFrame: {len(filtered_df)} rows, {filtered_df['CONVERSATION_ID'].nunique()} unique conversations")
    
    try:
        # Step 1: Fetch categorizing data from DOCTORS_CATEGORIZING_RAW_DATA
        categorizing_query = f"""
        SELECT 
            CONVERSATION_ID,
            LLM_RESPONSE
        FROM LLM_EVAL.PUBLIC.DOCTORS_CATEGORIZING_RAW_DATA
        WHERE DEPARTMENT = '{department_name}'
        AND DATE = '{target_date}'
        AND PROCESSING_STATUS = 'COMPLETED'
        AND LLM_RESPONSE IS NOT NULL
        AND LLM_RESPONSE != ''
        """
        
        print(f"   🔄 Fetching categorizing data for {department_name} on {target_date}...")
        categorizing_df = session.sql(categorizing_query).to_pandas()
        
        if categorizing_df.empty:
            print(f"   ⚠️  No categorizing data found for {department_name} on {target_date}")
            return pd.DataFrame()  # Return empty DataFrame
        
        print(f"   📋 Found {len(categorizing_df)} categorizing records")
        
        # Step 2: Parse JSON responses and find conversations with matching category/flags
        matching_conversation_ids = set()
        parsed_count = 0
        error_count = 0
        
        for _, row in categorizing_df.iterrows():
            try:
                conversation_id = row['CONVERSATION_ID']
                llm_response = row['LLM_RESPONSE']
                
                # Parse JSON response
                if isinstance(llm_response, str) and llm_response.strip():
                    # Clean the response if it has extra formatting
                    cleaned_response = llm_response.strip()
                    if cleaned_response.startswith('```json'):
                        cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
                    
                    response_data = json.loads(cleaned_response)

                    # Primary logic: for Doctors flows we filter by explicit flags rather than the 'category' list
                    # - For 'OTC Medication Advice' and 'Clinic Recommendation', include only if their value is affirmative
                    included = False
                    target_keys = ["OTC Medication Advice", "Clinic Recommendation"]

                    if category_name in target_keys:
                        val = response_data.get(category_name)
                        if isinstance(val, str):
                            included = val.strip().lower() in {"yes", "y", "true", "1"}
                        elif isinstance(val, bool):
                            included = val is True
                        elif isinstance(val, (int, float)):
                            included = (val == 1)
                    else:
                        # Fallback legacy behavior: use 'category' array for other category names
                        if 'category' in response_data:
                            categories = response_data['category']
                            if isinstance(categories, str):
                                categories = [categories]
                            if isinstance(categories, list) and category_name in categories:
                                included = True

                    if included:
                        matching_conversation_ids.add(conversation_id)
                    
                    parsed_count += 1
                
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                error_count += 1
                continue
        
        print(f"   ✅ Parsed {parsed_count} responses, {error_count} parsing errors")
        print(f"   🎯 Found {len(matching_conversation_ids)} conversations with category '{category_name}'")
        
        # Step 3: Filter the input DataFrame to only include matching conversations
        if not matching_conversation_ids:
            print(f"   ⚠️  No conversations found with category '{category_name}'")
            return pd.DataFrame()  # Return empty DataFrame
        
        # Filter the DataFrame
        filtered_result = filtered_df[filtered_df['CONVERSATION_ID'].isin(matching_conversation_ids)].copy()
        
        print(f"   📊 Final filtered result: {len(filtered_result)} rows, {filtered_result['CONVERSATION_ID'].nunique()} unique conversations")
        
        # Add category information for reference
        filtered_result['FILTER_CATEGORY'] = category_name
        filtered_result['FILTER_SOURCE'] = 'DOCTORS_CATEGORIZING_RAW_DATA'
        
        return filtered_result
        
    except Exception as e:
        error_details = format_error_details(e, f"FILTER BY CATEGORY - {category_name}")
        print(f"   ❌ Error filtering by category '{category_name}': {str(e)}")
        print(error_details)
        return pd.DataFrame()  # Return empty DataFrame on error


def test_llm_single_prompt(session: snowpark.Session, department_name, prompt_type, target_date=None, sample_size=1):
    """
    Test LLM analysis for a single prompt with a small sample
    
    Args:
        session: Snowflake session
        department_name: Department name
        prompt_type: Specific prompt type to test
        target_date: Target date for analysis
        sample_size: Number of conversations to test
    
    Returns:
        Test results
    """
    print(f"🧪 TESTING LLM ANALYSIS - {department_name} / {prompt_type}")
    print("=" * 60)
    
    try:
        # Get prompt configuration
        prompt_config = get_prompt_config(department_name, prompt_type)
        if not prompt_config:
            print(f"❌ Prompt configuration not found for {department_name}/{prompt_type}")
            return
        
        # Get a small sample of data
        dept_results, success = process_department_llm_analysis(session, department_name, target_date)
        
        if not success:
            print(f"❌ Failed to get sample data for {department_name}")
            return
        
        if prompt_type in dept_results:
            results = dept_results[prompt_type]
            print(f"\n📊 TEST RESULTS:")
            for key, value in results.items():
                print(f"   {key}: {value}")
        else:
            print(f"❌ No results for prompt type {prompt_type}")
            
    except Exception as e:
        error_details = format_error_details(e, f"LLM TEST - {department_name}/{prompt_type}")
        print(error_details)
