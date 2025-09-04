import snowflake.snowpark as snowpark
import ast
import traceback
from collections import Counter
from datetime import datetime
import json
import re
import pandas as pd
 

def get_tools_called(conversation_content):
    """
    Return a mapping of tool name -> number of invocations in a single conversation's content.

    Supports two formats:
      - JSON conversation: { "conversation": [ { "type": "tool", "tool": "name", ... } ... ] }
        Also supports messages containing 'tool_calls': [{ name | tool | tool_name }].
      - XML conversation: multiple <tool> blocks with <n>tool_name</n> inside.

    Args:
      conversation_content: str | dict | list — content in JSON or XML form

    Returns:
      dict[str, int]: tool name to count
    """
    tool_to_count = {}

    def bump(name):
        if name is None:
            return
        key = str(name).strip()
        if not key:
            return
        tool_to_count[key] = tool_to_count.get(key, 0) + 1

    # Try JSON path first
    try:
        parsed = None
        if isinstance(conversation_content, (dict, list)):
            parsed = conversation_content
        elif isinstance(conversation_content, str):
            s = conversation_content.strip()
            if s.startswith('{') or s.startswith('[') or s.startswith('```'):
                parsed = safe_json_parse(s)

        def scan_messages(messages):
            if not isinstance(messages, list):
                return
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                # Direct 'tool' field for tool-type messages
                if str(msg.get('type', '')).lower() == 'tool':
                    bump(msg.get('tool') or msg.get('name'))
    

        if isinstance(parsed, dict):
            scan_messages(parsed.get('conversation'))
            if tool_to_count:
                return tool_to_count
        elif isinstance(parsed, list):
            scan_messages(parsed)
            if tool_to_count:
                return tool_to_count
    except Exception:
        pass

    # Fallback: XML-like content
    try:
        from html import unescape as html_unescape
        import re
        text = conversation_content if isinstance(conversation_content, str) else str(conversation_content)
        # Find each <tool>...</tool> block and extract the first <n>...</n>
        for block in re.findall(r"<tool\b[\s\S]*?>[\s\S]*?<\/tool>", text, flags=re.IGNORECASE):
            m = re.search(r"<n\b[^>]*>([\s\S]*?)<\/n>", block, flags=re.IGNORECASE)
            if m:
                bump(html_unescape(m.group(1)))
        return tool_to_count
    except Exception:
        return tool_to_count


def generate_mv_resolvers_wrong_tool_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Generate WRONG_TOOL summary per conversation and tool.

    Reads LLM_EVAL.PUBLIC.WRONG_TOOL_RAW_DATA where LLM_RESPONSE has structure:
      { "toolCalled": [ { "toolName": str, "properlyCalled": "Yes"|"No", ... }, ... ] }

    Output (besides DATE, DEPARTMENT, TIMESTAMP) columns:
      - CONVERSATION_ID
      - TOOL_NAME
      - PROPERLY_CALLED_COUNT
      - TOTAL_COUNT
      - WRONG_TOOL_PERCENTAGE = (count(properlyCalled='No') / count(properlyCalled in {Yes, No})) * 100

    Returns (in order):
      - float: overall wrong-tool percentage across all items (No / (Yes+No) * 100)
      - int: global count of Not Properly Called (No)
      - str: standardized analysis summary JSON {chats_analyzed, chats_parsed, chats_failed, failure_percentage}
      - bool: success flag (insert completed or no data)
    """
    print(f"📊 Creating WRONG_TOOL summary for {department_name} on {target_date}...")
    try:
        # Step 1: Load raw data
        raw_query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.WRONG_TOOL_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROMPT_TYPE = 'mv_resolvers_wrong_tool'
          AND PROCESSING_STATUS = 'COMPLETED'
          AND LLM_RESPONSE IS NOT NULL
          AND LLM_RESPONSE != ''
        """
        raw_df = session.sql(raw_query).to_pandas()

        if raw_df.empty:
            print(f"   ℹ️  No WRONG_TOOL_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats, True

        print(f"   📈 Loaded {len(raw_df)} WRONG_TOOL rows from Snowflake")

        # Step 2: Aggregate per conversation and tool
        summary_rows = []
        parsed_rows = 0
        parse_errors = 0
        global_yes = 0
        global_no = 0

        for _, row in raw_df.iterrows():
            conversation_id = row['CONVERSATION_ID']
            llm_output = row['LLM_RESPONSE']
            parsed = None
            if isinstance(llm_output, (dict, list)):
                parsed = llm_output
            elif isinstance(llm_output, str) and llm_output.strip():
                parsed = safe_json_parse(llm_output)

            try:
                items = []
                if isinstance(parsed, dict):
                    tc = parsed.get('toolCalled')
                    if isinstance(tc, list):
                        items = tc
                elif isinstance(parsed, list):
                    # If top-level is a list, treat as array of tool calls
                    items = parsed

                # Count per tool
                per_tool_counts = {}
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    tool_name = str(it.get('toolName') or it.get('tool') or '').strip()
                    if not tool_name:
                        continue
                    properly = parse_boolean_flexible(it.get('properlyCalled'))
                    # Only count Yes/No; ignore None/unknown
                    if properly is None:
                        continue
                    entry = per_tool_counts.setdefault(tool_name, { 'yes': 0, 'no': 0 })
                    if properly is True:
                        entry['yes'] += 1
                        global_yes += 1
                    else:
                        entry['no'] += 1
                        global_no += 1

                for tool_name, counts in per_tool_counts.items():
                    total = counts['yes'] + counts['no']
                    wrong_pct = (counts['no'] / total * 100.0) if total > 0 else 0.0
                    summary_rows.append({
                        'CONVERSATION_ID': conversation_id,
                        'TOOL_NAME': tool_name,
                        'NOT_PROPERLY_CALLED_COUNT': int(counts['no']),
                        'TOTAL_COUNT': int(total),
                        'WRONG_TOOL_PERCENTAGE': round(wrong_pct, 1)
                    })
                parsed_rows += 1
            except Exception as e:
                parse_errors += 1
                continue

        if not summary_rows:
            print("   ⚠️  No summary rows generated for WRONG_TOOL")
            chats_analyzed = len(raw_df)
            chats_parsed = parsed_rows
            failure_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": chats_parsed,
                "chats_failed": chats_analyzed - chats_parsed,
                "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
            }, indent=2)
            denom = global_yes + global_no
            overall_wrong_pct = (global_no / denom * 100.0) if denom > 0 else 0.0
            return round(overall_wrong_pct, 1), global_no, failure_stats, True

        summary_df = pd.DataFrame(summary_rows)

        # Step 3: Insert into WRONG_TOOL_SUMMARY
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='WRONG_TOOL_SUMMARY',
            department=department_name,
            target_date=target_date,
            dataframe=summary_df,
            columns=list(summary_df.columns)
        )

        if not insert_success or insert_success.get('status') != 'success':
            print("   ❌ Failed to insert WRONG_TOOL summary data")
            chats_analyzed = len(raw_df)
            chats_parsed = parsed_rows
            failure_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": chats_parsed,
                "chats_failed": chats_analyzed - chats_parsed,
                "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
            }, indent=2)
            denom = global_yes + global_no
            overall_wrong_pct = (global_no / denom * 100.0) if denom > 0 else 0.0
            return round(overall_wrong_pct, 1), global_no, failure_stats, False

        chats_analyzed = len(raw_df)
        chats_parsed = parsed_rows
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": chats_parsed,
            "chats_failed": chats_analyzed - chats_parsed,
            "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)
        denom = global_yes + global_no
        overall_wrong_pct = (global_no / denom * 100.0) if denom > 0 else 0.0

        print(f"   ✅ WRONG_TOOL summary inserted: {len(summary_df)} rows (parsed={parsed_rows}, errors={parse_errors})")
        print(f"   📌 Overall WRONG_TOOL percentage: {overall_wrong_pct:.1f}% (No={global_no} / Yes+No={denom})")
        return round(overall_wrong_pct, 1), global_no, failure_stats, True
    except Exception as e:
        error_details = format_error_details(e, 'WRONG_TOOL SUMMARY REPORT')
        print(f"   ❌ Failed to create WRONG_TOOL summary report: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, empty_stats, False


def generate_mv_resolvers_missing_tool_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Generate MISSING_TOOL summary per conversation and tool.

    Reads LLM_EVAL.PUBLIC.MISSING_TOOL_RAW_DATA where LLM_RESPONSE has structure like:
      {
        "Tool #1": [
          {"shouldBeCalled": "Yes|No", "wasCalled": "Yes|No", "missedCall": "Yes|No", "toolName": "<name or N/A>", ...}
        ],
        "Tool #2": [ ... ]
      }

    Output (besides DATE, DEPARTMENT, TIMESTAMP) columns:
      - CONVERSATION_ID
      - TOOL_NAME
      - MISSED_CALLED_COUNT
      - SHOULD_BE_CALLED_COUNT
      - MISSING_TOOL_PERCENTAGE = (count(missedCall='Yes') / count(shouldBeCalled='Yes')) * 100

    Returns (in order):
      - float: overall missing-tool percentage across all items (missed / should * 100)
      - int: global count of missed calls
      - str: standardized analysis summary JSON {chats_analyzed, chats_parsed, chats_failed, failure_percentage}
      - bool: success flag
    """
    print(f"📊 Creating MISSING_TOOL summary for {department_name} on {target_date}...")
    try:
        # Step 1: Load raw data
        raw_query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.MISSING_TOOL_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROMPT_TYPE = 'mv_resolvers_missing_tool'
          AND PROCESSING_STATUS = 'COMPLETED'
          AND LLM_RESPONSE IS NOT NULL
          AND LLM_RESPONSE != ''
        """
        raw_df = session.sql(raw_query).to_pandas()

        if raw_df.empty:
            print(f"   ℹ️  No MISSING_TOOL_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats, True

        print(f"   📈 Loaded {len(raw_df)} MISSING_TOOL rows from Snowflake")

        # Step 2: Aggregate per conversation and tool
        summary_rows = []
        parsed_rows = 0
        parse_errors = 0
        global_missed = 0
        global_should = 0

        for _, row in raw_df.iterrows():
            conversation_id = row['CONVERSATION_ID']
            llm_output = row['LLM_RESPONSE']

            parsed = None
            if isinstance(llm_output, dict):
                parsed = llm_output
            elif isinstance(llm_output, str) and llm_output.strip():
                parsed = safe_json_parse(llm_output)
                # Fallback: attempt to fix malformed JSON where tool arrays lack object braces
                if parsed is None:
                    try:
                        cleaned = llm_output.strip()
                        # Remove markdown fences if present
                        if cleaned.startswith('```'):
                            cleaned = cleaned.replace('```json', '').replace('```', '').strip()
                        # Remove trailing commas before } or ]
                        cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
                        # Wrap arrays like "Tool #1": [ "k":"v", ... ] -> "Tool #1": [ { "k":"v", ... } ]
                        # Only apply when there is no '{' immediately after '[' for that tool block
                        pattern = re.compile(r'("Tool\s*#\d+"\s*:\s*)\[\s*(?!\{)(.*?)\s*\]', re.DOTALL)
                        def wrap_object(m):
                            inner = m.group(2)
                            return f"{m.group(1)}[{{{inner}}}]"
                        fixed = re.sub(pattern, wrap_object, cleaned)
                        parsed = json.loads(fixed)
                    except Exception:
                        parsed = None

            try:
                if not isinstance(parsed, dict):
                    raise ValueError('Unexpected JSON structure for MISSING_TOOL')

                # Build per-tool counters
                per_tool_counts = {}

                for key, value in parsed.items():
                    # value is expected to be a list of dicts
                    if not isinstance(value, list):
                        continue
                    for item in value:
                        if not isinstance(item, dict):
                            continue
                        # Determine tool name
                        raw_tool = item.get('toolName')
                        tool_name = None
                        if isinstance(raw_tool, str) and raw_tool.strip() and raw_tool.strip().upper() not in {'N/A', 'NA', 'NONE', 'NULL'}:
                            tool_name = raw_tool.strip()
                        else:
                            continue

                        should_be_called = parse_boolean_flexible(item.get('shouldBeCalled')) is True
                        missed_call = parse_boolean_flexible(item.get('missedCall')) is True

                        entry = per_tool_counts.setdefault(tool_name, { 'missed': 0, 'should': 0 })
                        if should_be_called:
                            entry['should'] += 1
                            global_should += 1
                            if missed_call:
                                entry['missed'] += 1
                                global_missed += 1

                # Emit rows
                for tool_name, counts in per_tool_counts.items():
                    denom = counts['should']
                    pct = (counts['missed'] / denom * 100.0) if denom > 0 else 0.0
                    summary_rows.append({
                        'CONVERSATION_ID': conversation_id,
                        'TOOL_NAME': tool_name,
                        'MISSED_CALLED_COUNT': int(counts['missed']),
                        'SHOULD_BE_CALLED_COUNT': int(counts['should']),
                        'MISSING_TOOL_PERCENTAGE': round(pct, 1)
                    })

                parsed_rows += 1
            except Exception:
                parse_errors += 1
                continue

        if not summary_rows:
            print("   ⚠️  No summary rows generated for MISSING_TOOL")
            chats_analyzed = len(raw_df)
            chats_parsed = parsed_rows
            failure_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": chats_parsed,
                "chats_failed": chats_analyzed - chats_parsed,
                "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
            }, indent=2)
            denom = global_should
            overall_missing_pct = (global_missed / denom * 100.0) if denom > 0 else 0.0
            return round(overall_missing_pct, 1), global_missed, failure_stats, True

        summary_df = pd.DataFrame(summary_rows)

        # Step 3: Insert into MISSING_TOOL_SUMMARY
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='MISSING_TOOL_SUMMARY',
            department=department_name,
            target_date=target_date,
            dataframe=summary_df,
            columns=list(summary_df.columns)
        )

        if not insert_success or insert_success.get('status') != 'success':
            print("   ❌ Failed to insert MISSING_TOOL summary data")
            chats_analyzed = len(raw_df)
            chats_parsed = parsed_rows
            failure_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": chats_parsed,
                "chats_failed": chats_analyzed - chats_parsed,
                "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
            }, indent=2)
            denom = global_should
            overall_missing_pct = (global_missed / denom * 100.0) if denom > 0 else 0.0
            return round(overall_missing_pct, 1), global_missed, failure_stats, False

        chats_analyzed = len(raw_df)
        chats_parsed = parsed_rows
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": chats_parsed,
            "chats_failed": chats_analyzed - chats_parsed,
            "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)
        denom = global_should
        overall_missing_pct = (global_missed / denom * 100.0) if denom > 0 else 0.0

        print(f"   ✅ MISSING_TOOL summary inserted: {len(summary_df)} rows (parsed={parsed_rows}, errors={parse_errors})")
        print(f"   📌 Overall MISSING_TOOL percentage: {overall_missing_pct:.1f}% (missed={global_missed} / should={denom})")
        return round(overall_missing_pct, 1), global_missed, failure_stats, True
    except Exception as e:
        error_details = format_error_details(e, 'MISSING_TOOL SUMMARY REPORT')
        print(f"   ❌ Failed to create MISSING_TOOL summary report: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, empty_stats, False


def get_tools_supposed_to_be_called_counts(llm_response):
    """
    Extract a mapping of tool name -> number of times it is supposed to be called
    from an LLM response with structure like:

    [
      {
        "chatId": "...",
        "transfer_chat": {"Supposed_To_Be_Called": true, "numberTimes_Supposed_To_Be_Called": 2, ...},
        "send_document": {"Supposed_To_Be_Called": false, ...},
        ...
      }
    ]

    Input can be a dict/list or a JSON string.
    Returns a dict of { tool_name: count }, including only tools where the
    supposed flag is truthy and the count > 0 (defaults to 1 if missing).
    """
    result = {}

    # Normalize input to a list[dict]
    try:
        parsed = None
        if isinstance(llm_response, (dict, list)):
            parsed = llm_response
        elif isinstance(llm_response, str) and llm_response.strip():
            parsed = safe_json_parse(llm_response)

        if isinstance(parsed, dict):
            items = [parsed]
        elif isinstance(parsed, list):
            items = parsed
        else:
            return result

        for obj in items:
            if not isinstance(obj, dict):
                continue
            for key, value in obj.items():
                # Skip meta keys
                if str(key).lower() in { 'chatid', 'chat_id', 'conversation_id' }:
                    continue
                if not isinstance(value, dict):
                    continue
                supposed = parse_boolean_flexible(value.get('Supposed_To_Be_Called'))
                if supposed is True:
                    num = value.get('numberTimes_Supposed_To_Be_Called')
                    try:
                        count = int(float(num)) if num is not None else 1
                    except Exception:
                        count = 1
                else:
                    count = 0
                result[str(key).strip()] = result.get(str(key).strip(), 0) + count
        return result
    except Exception:
        return result


def generate_tool_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Create tool summary per conversation with supposed vs actually called counts and percentages.

    Reads LLM_EVAL.PUBLIC.TOOL_RAW_DATA and expects columns including:
      - CONVERSATION_ID
      - LLM_RESPONSE (JSON as described)
      - CONVERSATION_CONTENT (XML or JSON of the conversation)

    Output columns (plus DATE, DEPARTMENT, TIMESTAMP):
      - CONVERSATION_ID
      - TOOL_NAME
      - SUPPOSED_TO_BE_CALLED_COUNT
      - ACTUALLY_CALLED_COUNT
      - WRONG_TOOL_PERCENTAGE
      - MISSING_TOOL_PERCENTAGE

    Returns (in order):
      - float: WRONG_TOOL_PERCENTAGE (overall) = sum(wrong) / sum(actual) * 100
      - int: WRONG_TOOL_COUNT (overall wrong count)
      - float: MISSING_TOOL_PERCENTAGE (overall) = sum(missed) / sum(supposed) * 100
      - int: MISSING_TOOL_COUNT (overall missed count)
      - str: TOOL_ANALYSIS_SUMMARY JSON {chats_analyzed, chats_parsed, chats_failed, failure_percentage}
      - bool: TOOL_SUMMARY_SUCCESS flag
    """
    print(f"📊 Creating TOOL summary report for {department_name} on {target_date}...")
    try:
        # Load raw rows for given date/department
        raw_query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS,
            CONVERSATION_CONTENT
        FROM LLM_EVAL.PUBLIC.TOOL_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROCESSING_STATUS = 'COMPLETED'
          AND LLM_RESPONSE IS NOT NULL
          AND LLM_RESPONSE != ''
        """
        raw_df = session.sql(raw_query).to_pandas()

        if raw_df.empty:
            print(f"   ℹ️  No TOOL_RAW_DATA data found for {department_name} on {target_date}")
            return True

        print(f"   📈 Loaded {len(raw_df)} TOOL rows from Snowflake")

        summary_rows = []
        parsed_rows = 0
        parse_errors = 0
        global_wrong = 0
        global_missing = 0
        denom_wrong = 0
        denom_missing = 0

        for _, row in raw_df.iterrows():
            conversation_id = row['CONVERSATION_ID']
            llm_output = row['LLM_RESPONSE']
            conversation_content = row.get('CONVERSATION_CONTENT', '')

            # Get actual tools called from content
            actual_counts = {}
            try:
                actual_counts = get_tools_called(conversation_content)
            except Exception:
                actual_counts = {}

            # Get supposed counts from LLM response
            supposed_counts = {}
            try:
                supposed_counts = get_tools_supposed_to_be_called_counts(llm_output)
            except Exception:
                supposed_counts = {}

            try:
                # For each tool present in supposed mapping, compute metrics
                for tool_name, supposed in supposed_counts.items():
                    actual = int(actual_counts.get(tool_name, 0))
                    supposed = int(supposed)
                    if supposed == 0 and actual == 0:
                        continue

                    tool_wrong = max(actual - supposed, 0)
                    tool_missed = max(supposed - actual, 0)

                    wrong_pct = (tool_wrong / actual * 100.0) if actual > 0 else 0.0
                    missing_pct = (tool_missed / supposed * 100.0) if supposed > 0 else 0.0

                    # Accumulate global totals for overall metrics
                    global_wrong += tool_wrong
                    global_missing += tool_missed
                    denom_wrong += max(actual, 0)
                    denom_missing += max(supposed, 0)

                    summary_rows.append({
                        'CONVERSATION_ID': conversation_id,
                        'TOOL_NAME': str(tool_name),
                        'SUPPOSED_TO_BE_CALLED_COUNT': supposed,
                        'ACTUALLY_CALLED_COUNT': actual,
                        'WRONG_TOOL_PERCENTAGE': round(wrong_pct, 1),
                        'MISSING_TOOL_PERCENTAGE': round(missing_pct, 1)
                    })
                parsed_rows += 1
            except Exception:
                parse_errors += 1
                continue

        if not summary_rows:
            print("   ⚠️  No summary rows generated for TOOL summary")
            return True

        summary_df = pd.DataFrame(summary_rows)

        # Insert into TOOL_SUMMARY table
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='TOOL_SUMMARY',
            department=department_name,
            target_date=target_date,
            dataframe=summary_df,
            columns=list(summary_df.columns)
        )

        if not insert_success or insert_success.get('status') != 'success':
            print("   ❌ Failed to insert TOOL summary data")
            chats_analyzed = len(raw_df)
            chats_parsed = parsed_rows
            failure_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": chats_parsed,
                "chats_failed": chats_analyzed - chats_parsed,
                "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
            }, indent=2)
            overall_wrong_pct = (global_wrong / denom_wrong * 100.0) if denom_wrong > 0 else 0.0
            overall_missing_pct = (global_missing / denom_missing * 100.0) if denom_missing > 0 else 0.0
            return round(overall_wrong_pct, 1), int(global_wrong), round(overall_missing_pct, 1), int(global_missing), failure_stats, False

        chats_analyzed = len(raw_df)
        chats_parsed = parsed_rows
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": chats_parsed,
            "chats_failed": chats_analyzed - chats_parsed,
            "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        overall_wrong_pct = (global_wrong / denom_wrong * 100.0) if denom_wrong > 0 else 0.0
        overall_missing_pct = (global_missing / denom_missing * 100.0) if denom_missing > 0 else 0.0

        print(f"   ✅ TOOL summary inserted: {len(summary_df)} rows (parsed={parsed_rows}, errors={parse_errors})")
        print(f"   📌 Overall WRONG_TOOL percentage: {overall_wrong_pct:.1f}% (wrong={global_wrong} / actual={denom_wrong})")
        print(f"   📌 Overall MISSING_TOOL percentage: {overall_missing_pct:.1f}% (missed={global_missing} / supposed={denom_missing})")
        return round(overall_wrong_pct, 1), int(global_wrong), round(overall_missing_pct, 1), int(global_missing), failure_stats, True
    except Exception as e:
        error_details = format_error_details(e, 'TOOL SUMMARY REPORT')
        print(f"   ❌ Failed to create TOOL summary report: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, 0.0, 0, empty_stats, False


def generate_at_filipina_tool_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Create AT_Filipina tool summary per conversation using false/missed trigger stats.

    Reads LLM_EVAL.PUBLIC.TOOL_RAW_DATA and expects columns including:
      - CONVERSATION_ID
      - LLM_RESPONSE (JSON like: { ToolName: { false_triggers: int, missed_triggers: int }, ... })
      - CONVERSATION_CONTENT (XML or JSON of the conversation)

    Output columns (plus DATE, DEPARTMENT, TIMESTAMP):
      - CONVERSATION_ID
      - TOOL_NAME
      - FALSE_TRIGGERS
      - MISSED_TRIGGERS
      - ACTUALLY_CALLED_COUNT
      - WRONG_TOOL_PERCENTAGE   = (false_triggers / ACTUALLY_CALLED_COUNT) * 100
      - MISSING_TOOL_PERCENTAGE = (missed_triggers / (ACTUALLY_CALLED_COUNT - false_triggers + missed_triggers)) * 100

    Returns (in order):
      - float: WRONG_TOOL_PERCENTAGE (overall) = sum(false_triggers)/sum(actual) * 100
      - int: FALSE_TRIGGER_COUNT (overall)
      - float: MISSING_TOOL_PERCENTAGE (overall) = sum(missed_triggers)/sum(actual - false_triggers + missed_triggers) * 100
      - int: MISSING_TRIGGER_COUNT (overall)
      - str: TOOL_ANALYSIS_SUMMARY JSON {chats_analyzed, chats_parsed, chats_failed, failure_percentage}
      - bool: TOOL_SUMMARY_SUCCESS flag
    """
    print(f"📊 Creating AT_Filipina TOOL summary report for {department_name} on {target_date}...")
    try:
        # Load raw rows for given date/department
        raw_query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS,
            CONVERSATION_CONTENT
        FROM LLM_EVAL.PUBLIC.TOOL_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROCESSING_STATUS = 'COMPLETED'
          AND LLM_RESPONSE IS NOT NULL
          AND LLM_RESPONSE != ''
        """
        raw_df = session.sql(raw_query).to_pandas()

        if raw_df.empty:
            print(f"   ℹ️  No TOOL_RAW_DATA data found for {department_name} on {target_date}")
            return True

        print(f"   📈 Loaded {len(raw_df)} TOOL rows from Snowflake")

        summary_rows = []
        parsed_rows = 0
        parse_errors = 0
        global_false_triggers = 0
        global_missed_triggers = 0
        denom_wrong = 0
        denom_missing = 0

        for _, row in raw_df.iterrows():
            conversation_id = row['CONVERSATION_ID']
            llm_output = row['LLM_RESPONSE']
            conversation_content = row.get('CONVERSATION_CONTENT', '')

            # Get actual tools called from content
            try:
                actual_counts = get_tools_called(conversation_content) or {}
            except Exception:
                actual_counts = {}

            # Parse LLM summary for tools
            try:
                if isinstance(llm_output, dict):
                    parsed = llm_output
                elif isinstance(llm_output, str) and llm_output.strip():
                    parsed = safe_json_parse(llm_output)
                else:
                    parsed = None

                if not isinstance(parsed, dict):
                    continue

                for tool_name, stats in parsed.items():
                    if not isinstance(stats, dict):
                        continue
                    false_triggers = 0
                    missed_triggers = 0
                    try:
                        ft = stats.get('false_triggers', 0)
                        mt = stats.get('missed_triggers', 0)
                        false_triggers = int(float(ft)) if ft is not None else 0
                        missed_triggers = int(float(mt)) if mt is not None else 0
                    except Exception:
                        pass

                    actual = int(actual_counts.get(tool_name, 0))
                    if actual == 0 and false_triggers == 0 and missed_triggers == 0:
                        continue
                    # Wrong% = false_triggers / actual
                    wrong_pct = (false_triggers / actual * 100.0) if actual > 0 else 0.0
                    # Missing% = missed_triggers / (actual - false_triggers + missed_triggers)
                    denom = (actual - false_triggers + missed_triggers)
                    missing_pct = (missed_triggers / denom * 100.0) if denom > 0 else 0.0

                    if false_triggers > actual:
                        print(f"   ⚠️  False triggers ({false_triggers}) > actual ({actual}) for {tool_name} in {conversation_id}")

                    # Accumulate global totals
                    global_false_triggers += false_triggers
                    global_missed_triggers += missed_triggers
                    denom_wrong += max(actual, 0)
                    denom_missing += max(denom, 0)

                    # Always emit a row (even if all zeros) to reflect analysis output
                    summary_rows.append({
                        'CONVERSATION_ID': conversation_id,
                        'TOOL_NAME': str(tool_name),
                        'FALSE_TRIGGERS': int(false_triggers),
                        'MISSED_TRIGGERS': int(missed_triggers),
                        'ACTUALLY_CALLED_COUNT': actual,
                        'WRONG_TOOL_PERCENTAGE': round(wrong_pct, 1),
                        'MISSING_TOOL_PERCENTAGE': round(missing_pct, 1)
                    })
                parsed_rows += 1
            except Exception:
                parse_errors += 1
                continue

        if not summary_rows:
            print("   ⚠️  No summary rows generated for AT_Filipina TOOL summary")
            return True

        summary_df = pd.DataFrame(summary_rows)

        # Insert into AT_FILIPINA_TOOL_SUMMARY table
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='AT_FILIPINA_TOOL_SUMMARY',
            department=department_name,
            target_date=target_date,
            dataframe=summary_df,
            columns=list(summary_df.columns)
        )

        if not insert_success or insert_success.get('status') != 'success':
            print("   ❌ Failed to insert AT_FILIPINA_TOOL summary data")
            chats_analyzed = len(raw_df)
            chats_parsed = parsed_rows
            failure_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": chats_parsed,
                "chats_failed": chats_analyzed - chats_parsed,
                "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
            }, indent=2)
            overall_wrong_pct = (global_false_triggers / denom_wrong * 100.0) if denom_wrong > 0 else 0.0
            overall_missing_pct = (global_missed_triggers / denom_missing * 100.0) if denom_missing > 0 else 0.0
            return round(overall_wrong_pct, 1), int(global_false_triggers), round(overall_missing_pct, 1), int(global_missed_triggers), failure_stats, False

        chats_analyzed = len(raw_df)
        chats_parsed = parsed_rows
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": chats_parsed,
            "chats_failed": chats_analyzed - chats_parsed,
            "failure_percentage": round(((chats_analyzed - chats_parsed) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        overall_wrong_pct = (global_false_triggers / denom_wrong * 100.0) if denom_wrong > 0 else 0.0
        overall_missing_pct = (global_missed_triggers / denom_missing * 100.0) if denom_missing > 0 else 0.0

        print(f"   ✅ AT_FILIPINA_TOOL summary inserted: {len(summary_df)} rows (parsed={parsed_rows}, errors={parse_errors})")
        print(f"   📌 Overall WRONG_TOOL percentage: {overall_wrong_pct:.1f}% (false={global_false_triggers} / actual={denom_wrong})")
        print(f"   📌 Overall MISSING_TOOL percentage: {overall_missing_pct:.1f}% (missed={global_missed_triggers} / denom={denom_missing})")
        return round(overall_wrong_pct, 1), int(global_false_triggers), round(overall_missing_pct, 1), int(global_missed_triggers), failure_stats, True
    except Exception as e:
        error_details = format_error_details(e, 'AT_FILIPINA TOOL SUMMARY REPORT')
        print(f"   ❌ Failed to create AT_FILIPINA TOOL summary report: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, 0.0, 0, empty_stats, False


def safe_json_parse(json_str):
    """
    Safely parse JSON strings with error handling - based on existing safe_json_loads patterns
    
    Args:
        json_str: JSON string to parse
    
    Returns:
        Parsed JSON object or None if parsing fails
    """
    try:
        if pd.isna(json_str):
            return None
        
        # Remove invisible unicode characters and strip whitespace
        cleaned = str(json_str).replace('\u202f', '').replace('\xa0', '').strip()
        
        # Handle empty or whitespace-only strings
        if not cleaned:
            return None
        
        # Clean JSON response (remove markdown formatting if present)
        if cleaned.startswith('```json'):
            cleaned = cleaned.replace('```json', '').replace('```', '').strip()
        elif cleaned.startswith('```'):
            cleaned = cleaned.replace('```', '').strip()
            
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError, Exception):
        return None


def parse_boolean_flexible(value):
    """
    Normalize heterogeneous boolean-like values to True/False.
    Supported inputs:
      - Python bool
      - 1/0 (int/float)
      - Strings like: 'true','t','yes','y','1' → True
                       'false','f','no','n','0' → False
    Returns:
      True | False when recognized, otherwise None.
    """
    try:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if value in (1, 1.0):
                return True
            if value in (0, 0.0):
                return False
            return None
        if isinstance(value, str):
            norm = value.strip().lower()
            if norm in {"true", "t", "yes", "y", "1"}:
                return True
            if norm in {"false", "f", "no", "n", "0"}:
                return False
            return None
        return None
    except Exception:
        return None


def get_department_agent_names_snowflake(session: snowpark.Session, department_name, departments_config):
    """
    Get agent names for a department from AGENTVIEW table based on skill matching.
    Returns a set of lowercase agent names.
    """
    try:
        dept_config = departments_config[department_name]
        agent_skills = dept_config['agent_skills']
        if not agent_skills:
            print(f"    ⚠️  {department_name}: No agent skills configured")
            return set()
        # Build exact match conditions for each skill in comma-separated string
        skill_conditions = []
        for skill in agent_skills:
            skill_upper = str(skill).upper()
            condition = f"""(
                UPPER(TRIM(SKILLNAME)) = '{skill_upper}' OR
                UPPER(TRIM(SKILLNAME)) LIKE '{skill_upper},%' OR
                UPPER(TRIM(SKILLNAME)) LIKE '%,{skill_upper},%' OR
                UPPER(TRIM(SKILLNAME)) LIKE '%,{skill_upper}' OR
                UPPER(TRIM(SKILLNAME)) LIKE '{skill_upper}, %' OR
                UPPER(TRIM(SKILLNAME)) LIKE '%, {skill_upper},%' OR
                UPPER(TRIM(SKILLNAME)) LIKE '%, {skill_upper}'
            )"""
            skill_conditions.append(condition)
        where_clause = " OR ".join(skill_conditions)
        query = f"""
        SELECT DISTINCT UPPER(AGENTNAME) as AGENTNAME
        FROM LLM_EVAL.RAW_DATA.AGENTVIEW
        WHERE ({where_clause})
          AND AGENTNAME IS NOT NULL
          AND AGENTNAME != ''
        """
        print(f"    🔍 {department_name}: Querying agents for skills: {agent_skills}")
        result = session.sql(query).collect()
        agent_names = {row['AGENTNAME'].lower().strip() for row in result if row['AGENTNAME']}
        print(f"    ✅ {department_name}: Found {len(agent_names)} agents")
        return agent_names
    except Exception as e:
        print(f"    ❌ {department_name}: Failed to get agent names - {str(e)}")
        return set()


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


def calculate_weighted_nps_average(nps_scores):
    """
    Calculate weighted average using the specified formula
    
    Args:
        nps_scores: List of NPS scores (1-5)
    
    Returns:
        Weighted average or 0 if no valid scores
    """
    if not nps_scores:
        return 0
    
    # Count NPS scores 1-5
    nps_counts = {i: nps_scores.count(i) for i in range(1, 6)}
    
    # Apply weighted formula
    numerator = (nps_counts[1]*2) + (nps_counts[2]*3) + (nps_counts[3]*3) + (nps_counts[4]*4) + (nps_counts[5]*10)
    denominator = (nps_counts[1]*2) + (nps_counts[2]*1.5) + (nps_counts[3]*1) + (nps_counts[4]*1) + (nps_counts[5]*2)
    
    return round(numerator / denominator, 2) if denominator > 0 else 0


def calculate_weighted_nps_per_department(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate weighted NPS average for a specific department from SA_RAW_DATA table
    
    Args:
        session: Snowflake session
        department_name: Name of the department to calculate NPS for
        target_date: Target date to filter SA_RAW_DATA records
    
    Returns:
        Float: Weighted average NPS for the department, or 0.0 if no data
    """
    print(f"📊 CALCULATING WEIGHTED NPS AVERAGES...")
    
    try:
        # Query SA_RAW_DATA table for target date, department, and SA_prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.SA_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'SA_prompt'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No SA_RAW_DATA data found for {department_name} on {target_date}")
            stats_json = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, stats_json
        
        print(f"   📊 Found {len(results_df)} SA_RAW_DATA records for {department_name} on {target_date}")
        
        nps_scores = []
        parsed_conversations = 0
            
        # Extract NPS scores for the department
        for _, row in results_df.iterrows():
            try:
                # Parse JSON/VARIANT response to extract NPS_score
                llm_response = row['LLM_RESPONSE']
                response_json = None
                if isinstance(llm_response, dict):
                    response_json = llm_response
                elif isinstance(llm_response, str) and llm_response.strip():
                    response_json = safe_json_parse(llm_response)
                
                if isinstance(response_json, dict):
                    parsed_conversations += 1
                    nps_score = response_json.get('NPS_score')
                    # Validate NPS score is in range 1-5
                    if isinstance(nps_score, (int, float)) and 1 <= nps_score <= 5:
                        nps_scores.append(int(float(nps_score)))
                    else:
                        print(f"   ⚠️  Invalid NPS score for {department_name}: {nps_score}")
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"   ⚠️  Failed to parse NPS from {department_name}: {str(e)}")
                print(f"   ⚠️  Failed to parse NPS from {department_name}: {llm_response}")
                continue
            
        # After processing all rows, build stats and compute
        chats_analyzed = len(results_df)
        chats_parsed = parsed_conversations
        chats_failed = chats_analyzed - chats_parsed
        failure_pct = round((chats_failed / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0

        stats_json = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": chats_parsed,
            "chats_failed": chats_failed,
            "failure_percentage": failure_pct
        }, indent=2)

        if nps_scores:
            weighted_avg = calculate_weighted_nps_average(nps_scores)
            print(f"   ✅ {department_name}: {len(nps_scores)} scores → weighted_AVG_SA = {weighted_avg:.2f}")
            return round(weighted_avg, 2), stats_json
        else:
            print(f"   ⚠️  {department_name}: No valid NPS scores found")
            return 0.0, stats_json
        
    except Exception as e:
        error_details = format_error_details(e, "WEIGHTED NPS CALCULATION")
        print(f"   ❌ Failed to calculate weighted NPS: {str(e)}")
        print(error_details)
        return 0.0, json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)


def calculate_call_request_metrics(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate call request metrics: call request rate and retention rate from call_request raw data.
    Skips failed parses in the denominator. Also returns parsing stats.
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter call request records
    
    Returns:
        Tuple: (call_request_rate, rebuttal_result_rate, stats_json)
        - call_request_rate: % of parsed chats where a call was requested
        - rebuttal_result_rate: % of requested calls that resulted in no retention (failure rate)
        - stats_json: pretty-printed JSON string of {"chats_analyzed", "chats_parsed", "chats_failed", "failure_percentage"}
    """
    print(f"📊 CALCULATING CALL REQUEST METRICS...")
    
    try:
        # Query CALL_REQUEST_RAW_DATA table for target date, department, and call_request prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.CALL_REQUEST_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'call_request'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No CALL_REQUEST_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats_json = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0.0, empty_stats_json, 0.0, 0.0
        
        print(f"   📊 Found {len(results_df)} call request records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0  # denominator
        call_requests_count = 0
        retained_count = 0
        no_retention_count = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                # Parse JSON response to extract call request data
                llm_response = row['LLM_RESPONSE']
                if not isinstance(llm_response, str) or not llm_response.strip():
                    # treat as failed parse (excluded from denominator)
                    continue
                
                # Parse using safe_json_parse to handle ```json fences and whitespace
                parsed = safe_json_parse(llm_response)
                if isinstance(parsed, dict):
                    parsed_conversations += 1
                    call_requested = str(parsed.get('CallRequested', '')).strip().lower()
                    if call_requested == 'true':
                        call_requests_count += 1
                        rebuttal_result = str(
                            parsed.get('CallRequestRebuttalResult', parsed.get('CallRequestRebutalResult', ''))
                        ).strip()
                        if rebuttal_result == 'Retained':
                            retained_count += 1
                        elif rebuttal_result == 'NoRetention':
                            no_retention_count += 1
                elif isinstance(parsed, bool):
                    parsed_conversations += 1
                    if parsed:
                        call_requests_count += 1
                        print(f"   📝 Processed boolean response: {parsed} (no rebuttal info)")
                elif isinstance(parsed, str):
                    normalized = parsed.strip().lower()
                    if normalized in {'true', 'false'}:
                        parsed_conversations += 1
                    if normalized == 'true':
                        call_requests_count += 1
                        print(f"   📝 Processed simple string response: {parsed} (no rebuttal info)")
                
            except Exception as e:
                print(f"   ⚠️  Error processing call request response: {str(e)}")
                continue
        
        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for call request analysis (all failed to parse)")
            failure_stats = {
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0,
            }
            failure_stats_json = json.dumps(failure_stats, indent=2)
            return 0.0, 0.0, failure_stats_json, 0.0, 0.0
        
        # Calculate metrics
        call_request_rate = (call_requests_count / parsed_conversations) * 100
        
        # Rebuttal result: percentage of call requests that resulted in no retention (failure rate)
        if call_requests_count > 0:
            rebuttal_result_rate = (no_retention_count / parsed_conversations) * 100
        else:
            rebuttal_result_rate = 0.0
        
        failure_stats = {
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0,
        }
        failure_stats_json = json.dumps(failure_stats, indent=2)
        
        print(f"   📈 Call Request Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Successfully parsed: {parsed_conversations}")
        print(f"   Failed to parse: {failure_stats['chats_failed']} ({failure_stats['failure_percentage']:.1f}%)")
        print(f"   Call requests made: {call_requests_count}")
        print(f"   Successfully retained: {retained_count}")
        print(f"   Not retained: {no_retention_count}")
        print(f"   Call request rate: {call_request_rate:.1f}%")
        print(f"   Rebuttal result rate (no retention): {rebuttal_result_rate:.1f}%")
        
        return round(call_request_rate, 1), call_requests_count, failure_stats_json, round(rebuttal_result_rate, 1),  no_retention_count
        
    except Exception as e:
        error_details = format_error_details(e, "CALL REQUEST METRICS CALCULATION")
        print(f"   ❌ Failed to calculate call request metrics: {str(e)}")
        print(error_details)
        return 0.0, 0.0, json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2), 0.0, 0.0
    

def calculate_legal_metrics(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate legal alignment metrics: escalation rate and legal concerns percentage from legal_alignment raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter legal alignment records
    
    Returns:
        Tuple: (escalation_rate, legal_concerns_percentage) or (0.0, 0.0) if no data
    """
    print(f"📊 CALCULATING LEGAL ALIGNMENT METRICS...")
    
    try:
        # Query LEGAL_ALIGNMENT_RAW_DATA table for target date, department, and legal_alignment prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.LEGAL_ALIGNMENT_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'legal_alignment'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No LEGAL_ALIGNMENT_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0.0, empty_stats
        
        print(f"   📊 Found {len(results_df)} legal alignment records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0
        legal_concerns_count = 0
        escalated_count = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                # Parse JSON response to extract legal alignment data
                llm_response = row['LLM_RESPONSE']
                if not isinstance(llm_response, str) or not llm_response.strip():
                    continue
                
                # Parse using safe_json_parse to handle ```json fences and whitespace
                parsed = safe_json_parse(llm_response)
                if isinstance(parsed, dict):
                    parsed_conversations += 1
                    legality_concerned = parse_boolean_flexible(parsed.get('LegalityQuestioned', ''))
                    if legality_concerned is True:
                        legal_concerns_count += 1
                        escalation_outcome = str(parsed.get('EscalationOutcome', '')).strip()
                        if escalation_outcome.lower() == 'escalated':
                            escalated_count += 1
                elif isinstance(parsed, bool):
                    parsed_conversations += 1
                    if parsed:
                        legal_concerns_count += 1
                        print(f"   📝 Processed boolean response: {parsed} (no escalation info)")
                elif isinstance(parsed, str):
                    normalized = parsed.strip().lower()
                    if normalized in {'true', 'false'}:
                        parsed_conversations += 1
                    if parse_boolean_flexible(normalized) is True:
                        legal_concerns_count += 1
                        print(f"   📝 Processed simple string response: {parsed} (no escalation info)")
                
            except Exception as e:
                print(f"   ⚠️  Error processing legal response: {str(e)}")
                continue
        
        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for legal alignment analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0.0, empty_stats
        
        # Metric 1: (EscalationOutcome = Escalated / LegalityConcerned = True) * 100
        escalation_rate = 0.0
        if legal_concerns_count > 0:
            escalation_rate = (escalated_count / legal_concerns_count) * 100
        
        # Metric 2: (LegalityConcerned = true / Total Output) * 100
        legal_concerns_percentage = (legal_concerns_count / parsed_conversations) * 100
        
        print(f"   📈 Legal Alignment Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Legal concerns identified: {legal_concerns_count}")
        print(f"   Cases escalated: {escalated_count}")
        print(f"   Escalation rate: {escalation_rate:.1f}% (escalated/legal concerns)")
        print(f"   Legal concerns percentage: {legal_concerns_percentage:.1f}% (legal concerns/total)")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round((escalation_rate / 100) * legal_concerns_percentage, 1), round(legal_concerns_percentage, 1), failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "LEGAL ALIGNMENT METRICS CALCULATION")
        print(f"   ❌ Failed to calculate legal alignment metrics: {str(e)}")
        print(error_details)
        return 0.0, 0.0
    

def calculate_client_suspecting_ai_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate percentage of conversations where client suspected AI from client_suspecting_ai raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter client suspecting AI records
    
    Returns:
        Float: Percentage of conversations where client suspected AI, or 0.0 if no data
    """
    print(f"📊 CALCULATING CLIENT SUSPECTING AI PERCENTAGE...")
    
    try:
        # Query CLIENT_SUSPECTING_AI_RAW_DATA table for target date, department, and client_suspecting_ai prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.CLIENT_SUSPECTING_AI_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'client_suspecting_ai'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No CLIENT_SUSPECTING_AI_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, empty_stats
        
        print(f"   📊 Found {len(results_df)} client suspecting AI records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0
        suspected_ai_count = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                # Parse JSON response to extract client suspecting AI data
                llm_response = row['LLM_RESPONSE']
                if not isinstance(llm_response, str) or not llm_response.strip():
                    print(f"   ⚠️  Empty LLM response: {repr(llm_response)}")
                    continue
                
                # Try JSON parsing first
                try:
                    response_json = safe_json_parse(llm_response)
                    if not isinstance(response_json, (dict, bool, str)):
                        raise ValueError('Unrecognized response type')
                    # Handle JSON format
                    client_suspecting = None
                    if isinstance(response_json, dict):
                        parsed_conversations += 1
                        client_suspecting = response_json.get('ClientSuspectingAI', response_json.get('client_suspecting_ai', ''))
                        client_suspecting = parse_boolean_flexible(client_suspecting)
                    elif isinstance(response_json, bool):
                        parsed_conversations += 1
                        client_suspecting = parse_boolean_flexible(response_json)
                    elif isinstance(response_json, str):
                        normalized = response_json.strip().lower()
                        if normalized in {'true', 'false'}:
                            parsed_conversations += 1
                        client_suspecting = parse_boolean_flexible(response_json)
                    
                    if client_suspecting is True:
                            suspected_ai_count += 1
                except Exception:
                    # Handle simple string responses (fallback)
                    normalized = llm_response.strip().lower()
                    if normalized in {'true', 'false'}:
                        parsed_conversations += 1
                    if parse_boolean_flexible(normalized) is True:
                        suspected_ai_count += 1
                except Exception:
                    # If all parsing fails, treat as False
                    pass
                
            except Exception as e:
                print(f"   ⚠️  Error processing response: {str(e)}")
                print(f"   🔍 Raw LLM response: {repr(llm_response[:200])}")
                continue
        
        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for client suspecting AI analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, empty_stats
        
        # Calculate percentage
        percentage = (suspected_ai_count / parsed_conversations) * 100
        
        print(f"   📈 Client Suspecting AI Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Suspected AI: {suspected_ai_count}")
        print(f"   Percentage: {percentage:.1f}%")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage, 1), failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "CLIENT SUSPECTING AI PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate client suspecting AI percentage: {str(e)}")
        print(error_details)
        return 0.0
    
def calculate_overall_percentages(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate overall % Transfer and % Intervention from categorizing raw data
    AND create detailed categorizing summary table
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter categorizing records
    
    Returns:
        Tuple: (intervention_percentage, transfer_percentage) or (0.0, 0.0) if no data
    """
    print(f"📊 CALCULATING OVERALL INTERVENTION/TRANSFER PERCENTAGES AND CATEGORIZING SUMMARY...")
    
    try:
        # Step 1: Analyze categorizing data from Snowflake
        parsed_df = analyze_categorizing_data_snowflake(session, department_name, target_date)
        
        if parsed_df is None or parsed_df.empty:
            print(f"   ℹ️  No categorizing data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0.0, empty_stats
        
        # Step 2: Create detailed categorizing summary table
        print(f"📊 Creating detailed categorizing summary table...")
        summary_success, summary_stats = create_categorizing_summary_report(session, parsed_df, department_name, target_date)
        
        if summary_success:
            print(f"   ✅ Categorizing summary table created successfully")
            print(f"       Categories analyzed: {summary_stats.get('total_categories', 0)}")
            print(f"       Summary rows inserted: {summary_stats.get('rows_inserted', 0)}")
        else:
            print(f"   ⚠️  Failed to create summary table: {summary_stats.get('error', 'Unknown error')}")
        
        # Step 3: Calculate overall intervention/transfer percentages 
        # (this is the core functionality that was already implemented)
        total_conversations = len(parsed_df)
        intervention_count = len(parsed_df[parsed_df['intervention_or_transfer'] == 'Intervention'])
        transfer_count = len(parsed_df[parsed_df['intervention_or_transfer'] == 'Transfer'])
        
        if total_conversations == 0:
            print("   ⚠️  No valid conversations found for intervention/transfer analysis")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0.0, empty_stats
        
        # Calculate percentages based on total conversations
        pct_intervention = (intervention_count / total_conversations) * 100
        pct_transfer = (transfer_count / total_conversations) * 100
        
        print(f"\n   📈 Overall Intervention/Transfer Results:")
        print(f"   Total conversations analyzed: {total_conversations}")
        print(f"   Interventions: {intervention_count} ({pct_intervention:.1f}% of all conversations)")
        print(f"   Transfers: {transfer_count} ({pct_transfer:.1f}% of all conversations)")
        print(f"   Other/Neither: {total_conversations - intervention_count - transfer_count}")
        
        # For this metric, treat all rows in parsed_df as parsed
        chats_analyzed = total_conversations
        parsed_conversations = total_conversations
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": 0.0
        }, indent=2)

        return round(pct_intervention, 1), round(pct_transfer, 1), failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "INTERVENTION/TRANSFER PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate intervention/transfer percentages: {str(e)}")
        print(error_details)
        return 0.0, 0.0
    
def calculate_false_promises_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate % False Promises (RogueAnswer count / Total conversations * 100) from false_promises raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter false promises records
    
    Returns:
        Float: Percentage of conversations with false promises, or 0.0 if no data
    """
    print(f"📊 CALCULATING FALSE PROMISES PERCENTAGE...")
    
    try:
        # Query FALSE_PROMISES_RAW_DATA table for target date, department, and false_promises prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.FALSE_PROMISES_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'false_promises'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No FALSE_PROMISES_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, empty_stats
        
        print(f"   📊 Found {len(results_df)} false promises records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0
        rogue_count = 0
        normal_count = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                # Parse JSON response to extract chat resolution data
                llm_response = row['LLM_RESPONSE']
                if not isinstance(llm_response, str) or not llm_response.strip():
                    continue
                
                response_json = safe_json_parse(llm_response)
                if response_json is None:
                    continue
                parsed_conversations += 1
                
                # Handle both object and array formats
                chat_resolution = ''
                
                if isinstance(response_json, dict):
                    # Handle object format: {"chatResolution": "RogueAnswer"}
                    chat_resolution = response_json.get('chatResolution', '').strip()
                elif isinstance(response_json, list) and len(response_json) > 0:
                    # Handle array format: ["RogueAnswer"] or [{"chatResolution": "RogueAnswer"}]
                    first_item = response_json[0]
                    if isinstance(first_item, str):
                        chat_resolution = first_item.strip()
                    elif isinstance(first_item, dict):
                        chat_resolution = first_item.get('chatResolution', '').strip()
                else:
                    # Unknown format, skip
                    print(f"   ⚠️  Unexpected JSON format: {type(response_json)} - {response_json}")
                    continue
                
                if chat_resolution == 'RogueAnswer':
                    rogue_count += 1
                elif chat_resolution == 'NormalAnswer':
                    normal_count += 1
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"   ⚠️  Failed to parse false promises data: {str(e)}")
                continue
        
        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for false promises analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, empty_stats
        
        # Calculate percentage: RogueAnswer / Total Conversations * 100
        false_promises_pct = (rogue_count / parsed_conversations) * 100
        
        print(f"   📈 False Promises Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   RogueAnswer (False Promises): {rogue_count}")
        print(f"   NormalAnswer: {normal_count}")
        print(f"   % False Promises: {false_promises_pct:.1f}% (RogueAnswer/Total)")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(false_promises_pct, 1), failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "FALSE PROMISES PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate false promises percentage: {str(e)}")
        print(error_details)
        return 0.0

def analyze_categorizing_data_snowflake(session: snowpark.Session, department_name: str, target_date):
    """
    Analyze categorizing prompt results from Snowflake table and return parsed DataFrame
        
        Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter categorizing records
    
    Returns:
        DataFrame with parsed categorizing results or None if no data
    """
    print(f"📊 Analyzing categorizing results from Snowflake for {department_name} on date: {target_date}")
    
    try:
        # Query CATEGORIZING_RAW_DATA table for target date, department, and categorizing prompt only
        query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.CATEGORIZING_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND (PROMPT_TYPE = 'categorizing' OR PROMPT_TYPE = 'intervention')
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No CATEGORIZING_RAW_DATA data found for {department_name} on {target_date}")
            return None
        
        print(f"   📈 Loaded {len(results_df)} conversations from Snowflake")
        
        # Parse JSON outputs
        parsed_results = []
        parse_errors = 0
        
        for idx, row in results_df.iterrows():
            llm_output = row['LLM_RESPONSE']
            parsed = safe_json_parse(llm_output)
            
            if parsed:
                # Extract categories list and intervention/transfer info
                categories_data = parsed.get('Categories', [])
                intervention_or_transfer = parsed.get('InterventionOrTransfer', 'N/A')
                category_causing = parsed.get('CategoryCausingInterventionOrTransfer', 'N/A')
                
                # Handle different possible formats for Categories
                categories_list = []
                if isinstance(categories_data, list):
                    for cat in categories_data:
                        if isinstance(cat, dict) and 'CategoryName' in cat:
                            categories_list.append(cat['CategoryName'])
                        elif isinstance(cat, str):
                            # Handle simple string format
                            categories_list.append(cat)
                elif isinstance(categories_data, dict):
                    # If it's a single category as dict
                    if 'CategoryName' in categories_data:
                        categories_list.append(categories_data['CategoryName'])
                
                parsed_results.append({
                    'chat_id': row['CONVERSATION_ID'],
                    'department': row['DEPARTMENT'],
                    'categories': categories_list,
                    'intervention_or_transfer': intervention_or_transfer,
                    'category_causing_intervention_transfer': category_causing,
                    'original_output': llm_output
                })
            else:
                parse_errors += 1
                # Still add to results for counting
                parsed_results.append({
                    'chat_id': row['CONVERSATION_ID'],
                    'department': row['DEPARTMENT'],
                    'categories': [],
                    'intervention_or_transfer': 'Parse_Error',
                    'category_causing_intervention_transfer': 'Parse_Error',
                    'original_output': llm_output
                })
        
        print(f"   ✅ Successfully parsed: {len(parsed_results) - parse_errors}/{len(results_df)} conversations")
        if parse_errors > 0:
            print(f"   ⚠️  Parse errors: {parse_errors}")
        
        # Create results DataFrame
        parsed_df = pd.DataFrame(parsed_results)
        
        # Print intervention/transfer breakdown
        intervention_counts = Counter(parsed_df['intervention_or_transfer'])
        print(f"\n   🔄 Intervention/Transfer Breakdown:")
        for int_type, count in intervention_counts.most_common():
            percentage = (count / len(parsed_df)) * 100
            print(f"     {int_type}: {count} ({percentage:.1f}%)")
        
        return parsed_df
        
    except Exception as e:
        error_details = format_error_details(e, "CATEGORIZING DATA ANALYSIS")
        print(f"   ❌ Failed to analyze categorizing data: {str(e)}")
        print(error_details)
        return None


def calculate_ftr_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate overall FTR (First Time Resolution) percentage from FTR raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter FTR records
    
    Returns:
        Float: Overall FTR percentage, or 0.0 if no data
    """
    print(f"📊 CALCULATING FTR PERCENTAGE...")
    
    try:
        # Query FTR_RAW_DATA table for target date, department, and FTR prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.FTR_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'ftr'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No FTR_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, empty_stats
        
        print(f"   📊 Found {len(results_df)} FTR records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0
        total_resolved_chats = 0
        total_parsed_conversations = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                # Parse JSON response to extract FTR data
                llm_response = row['LLM_RESPONSE']

                # Accept both Snowflake VARIANT (already parsed list/dict) and stringified JSON
                if isinstance(llm_response, (list, dict)):
                    parsed_response = llm_response
                elif isinstance(llm_response, str) and llm_response.strip():
                    parsed_response = safe_json_parse(llm_response)
                else:
                    continue

                # Expect a list; support both old ["Yes","No",...] and new [{"chatResolution":"Yes",...}, ...]
                if parsed_response and isinstance(parsed_response, list):
                    total_parsed_conversations += 1
                    yes_count = 0
                    item_count = 0
                    for item in parsed_response:
                        if isinstance(item, dict):
                            val = item.get('chatResolution')
                            if isinstance(val, str):
                                item_count += 1
                                if val.strip().lower() == 'yes':
                                    yes_count += 1
                        elif isinstance(item, str):
                            item_count += 1
                            if item.strip().lower() == 'yes':
                                yes_count += 1
                        elif isinstance(item, bool):
                            # If boolean format ever used, treat True as Yes
                            item_count += 1
                            if item:
                                yes_count += 1

                    parsed_conversations += item_count
                    total_resolved_chats += yes_count

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"   ⚠️  Failed to parse FTR data: {str(e)}")
                continue
        
        if total_parsed_conversations == 0:
            print("   ⚠️  No valid chats found for FTR analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, empty_stats
        
        # Calculate FTR percentage: Resolved chats / Total chats * 100
        # Note: Here each parsed row represents a conversation; success counted if any 'Yes' in array
        ftr_percentage = (total_resolved_chats / parsed_conversations) * 100
        
        print(f"   📈 FTR Analysis Results:")
        print(f"   Total chats analyzed: {chats_analyzed}")
        print(f"   Total resolved chats: {total_resolved_chats}")
        print(f"   Total parsed conversations: {total_parsed_conversations}")
        print(f"   Overall FTR percentage: {ftr_percentage:.1f}%")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": total_parsed_conversations,
            "chats_failed": chats_analyzed - total_parsed_conversations,
            "failure_percentage": round(((chats_analyzed - total_parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(ftr_percentage, 1), failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "FTR PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate FTR percentage: {str(e)}")
        print(error_details)
        return 0.0

def calculate_misprescription_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate overall misprescription percentage from misprescription raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter misprescription records
    
    Returns:
        Tuple: (misprescription_percentage, count) or (0.0, 0) if no data
    """
    print(f"📊 CALCULATING MISPRESCRIPTION PERCENTAGE...")
    
    try:
        # Query misprescription raw data table for target date, department, and misprescription prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.DOCTORS_MISPRESCRIPTION_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'misprescription'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No MISPRESCRIPTION_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        print(f"   📊 Found {len(results_df)} misprescription records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0
        misprescription_count = 0
        parsing_errors = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                llm_response = row['LLM_RESPONSE']
                if not isinstance(llm_response, str) or not llm_response.strip():
                    continue
                
                # Parse the JSON output
                parsed_result = safe_json_parse(llm_response)
                
                if parsed_result:
                    parsed_conversations += 1
                    # Handle both string and boolean values for mis-prescription
                    mis_prescription = parse_boolean_flexible(parsed_result.get('mis-prescription', False))
                    if mis_prescription is True:
                        misprescription_count += 1
                else:
                    parsing_errors += 1
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"   ⚠️  Failed to parse misprescription data: {str(e)}")
                parsing_errors += 1
                continue
        
        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for misprescription analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        # Calculate misprescription percentage: Misprescription cases / Total conversations * 100
        percentage = (misprescription_count / parsed_conversations) * 100
        
        print(f"   📈 Misprescription Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Misprescription cases found: {misprescription_count}")
        print(f"   Parsing errors: {parsing_errors}")
        print(f"   Overall misprescription percentage: {percentage:.1f}%")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage, 1), misprescription_count, failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "MISPRESCRIPTION PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate misprescription percentage: {str(e)}")
        print(error_details)
        return 0.0, 0

def calculate_unnecessary_clinic_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate overall unnecessary clinic recommendation percentage from unnecessary clinic raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter unnecessary clinic records
    
    Returns:
        Tuple: (unnecessary_clinic_percentage, count) or (0.0, 0) if no data
    """
    print(f"📊 CALCULATING UNNECESSARY CLINIC RECOMMENDATION PERCENTAGE...")
    
    try:
        # Query unnecessary clinic raw data table for target date, department, and unnecessary_clinic prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.DOCTORS_UNNECESSARY_CLINIC_RAW_DATA
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'unnecessary_clinic'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No UNNECESSARY_CLINIC_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        print(f"   📊 Found {len(results_df)} unnecessary clinic records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0
        could_avoid_count = 0
        parsing_errors = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                llm_response = row['LLM_RESPONSE']
                if not isinstance(llm_response, str) or not llm_response.strip():
                    continue
                
                # Parse the JSON output
                parsed_result = safe_json_parse(llm_response)
                
                if parsed_result:
                    parsed_conversations += 1
                    # Handle both string and boolean values for could_avoid_visit
                    could_avoid_visit = parse_boolean_flexible(parsed_result.get('could_avoid_visit', False))
                    if could_avoid_visit is True:
                        could_avoid_count += 1
                else:
                    parsing_errors += 1
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"   ⚠️  Failed to parse unnecessary clinic data: {str(e)}")
                parsing_errors += 1
                continue
        
        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for unnecessary clinic analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        # Calculate unnecessary clinic percentage: Could avoid cases / Total conversations * 100
        percentage = (could_avoid_count / parsed_conversations) * 100
        
        print(f"   📈 Unnecessary Clinic Recommendation Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Could avoid visit cases: {could_avoid_count}")
        print(f"   Parsing errors: {parsing_errors}")
        print(f"   Overall unnecessary clinic recommendation percentage: {percentage:.1f}%")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage, 1), could_avoid_count, failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "UNNECESSARY CLINIC PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate unnecessary clinic percentage: {str(e)}")
        print(error_details)
        return 0.0, 0

def calculate_clarity_score_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate clarity score percentage from clarity raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter clarity records
    
    Returns:
        Tuple: (clarification_percentage, total_clarifications) or (0.0, 0) if no data
    """
    print(f"📊 CALCULATING CLARITY SCORE PERCENTAGE...")
    
    try:
        # Query clarity raw data table for target date, department, and clarity prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.CLARITY_SCORE_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'clarity_score'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
            
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No CLARITY_SCORE_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        print(f"   📊 Found {len(results_df)} clarity records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        valid_responses = 0
        total_messages = 0
        total_clarifications = 0
        parsing_errors = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                llm_response = row['LLM_RESPONSE']
                if not isinstance(llm_response, str) or not llm_response.strip():
                    continue
                
                # Parse the JSON output
                parsed_result = safe_json_parse(llm_response)
                
                if parsed_result and isinstance(parsed_result, dict):
                    if ('TotalConsumer' in parsed_result or 'Total' in parsed_result)  and ('ClarificationMessagesTotal' in parsed_result or 'ClarificationMessages' in parsed_result):
                        try:
                            total = int(parsed_result['TotalConsumer'] if 'TotalConsumer' in parsed_result else parsed_result['Total'])
                            clarifications = int(parsed_result['ClarificationMessagesTotal'] if 'ClarificationMessagesTotal' in parsed_result else parsed_result['ClarificationMessages'])
                            
                            if total > 0:  # Valid conversation
                                total_messages += total
                                total_clarifications += clarifications
                                valid_responses += 1
                        except (ValueError, TypeError):
                            print(f"   ⚠️  Failed to parse clarity data: {parsed_result}")
                            parsing_errors += 1
                            continue
                    else:
                        print(f"   ⚠️  Failed to parse clarity data: {parsed_result}")
                        parsing_errors += 1
                else:
                    print(f"   ⚠️  Failed to parse clarity data: {parsed_result}")
                    parsing_errors += 1
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"   ⚠️  Failed to parse clarity data: {str(e)}")
                parsing_errors += 1
                continue
        
        if valid_responses == 0:
            print("   ⚠️  No valid clarity data found for analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        # Calculate clarification percentage: (clarification messages / total messages) * 100
        clarification_percentage = (total_clarifications / total_messages) * 100
        
        print(f"   📈 Clarity Score Analysis Results:")
        print(f"   Total conversations analyzed: {valid_responses}/{chats_analyzed}")
        print(f"   Total customer messages: {total_messages}")
        print(f"   Clarification requests: {total_clarifications}")
        print(f"   Parsing errors: {parsing_errors}")
        print(f"   Overall clarification percentage: {clarification_percentage:.1f}%")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": valid_responses,
            "chats_failed": chats_analyzed - valid_responses,
            "failure_percentage": round(((chats_analyzed - valid_responses) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(clarification_percentage, 1), total_clarifications, failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "CLARITY SCORE PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate clarity score percentage: {str(e)}")
        print(error_details)
        return 0.0, 0

def calculate_threatening_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate threatening behavior percentage from threatening raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter threatening records
    
    Returns:
        Tuple: (threatening_percentage, threatening_count) or (0.0, 0) if no data
    """
    print(f"📊 CALCULATING THREATENING BEHAVIOR PERCENTAGE...")
    
    try:
        # Query threatening raw data table for target date, department, and threatening prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS,
            CONVERSATION_ID
        FROM LLM_EVAL.PUBLIC.THREATENING_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'threatening'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No THREATENING_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        print(f"   📊 Found {len(results_df)} threatening records for {department_name} on {target_date}")
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0
        threatening_count = 0

        # Process each record; new format is JSON object {"Result": "Yes"|"No", ...}
        # Keep backward compatibility with previous boolean-like outputs
        for _, row in results_df.iterrows():
            llm_response = row['LLM_RESPONSE']

            value_is_true = None  # None = unrecognized, True/False = recognized

            # If Snowflake returns VARIANT as dict
            if isinstance(llm_response, dict):
                result_val = llm_response.get('Result')
                if result_val is not None:
                    value_is_true = parse_boolean_flexible(result_val if isinstance(result_val, str) else result_val)
            # If string, attempt JSON parse first, then fallback to boolean-like string
            elif isinstance(llm_response, str) and llm_response.strip():
                parsed = safe_json_parse(llm_response)
                if isinstance(parsed, dict) and 'Result' in parsed:
                    value_is_true = parse_boolean_flexible(parsed.get('Result'))
                else:
                    normalized = llm_response.strip().lower()
                    value_is_true = parse_boolean_flexible(normalized)
            # Handle native booleans and numeric representations
            elif isinstance(llm_response, bool):
                value_is_true = llm_response
            elif isinstance(llm_response, (int, float)):
                value_is_true = parse_boolean_flexible(llm_response)

            # Count only recognized values
            if value_is_true is not None:
                parsed_conversations += 1
                if value_is_true:
                    threatening_count += 1
        
        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for threatening analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        # Calculate threatening percentage: Threatening cases / Total conversations * 100
        percentage = (threatening_count / parsed_conversations) * 100
        
        print(f"   📈 Threatening Behavior Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Threatening cases found: {threatening_count}")
        print(f"   Overall threatening percentage: {percentage:.1f}%")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage, 1), threatening_count, failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "THREATENING PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate threatening percentage: {str(e)}")
        print(error_details)
        return 0.0, 0

def calculate_policy_escalation_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate policy escalation percentage from policy escalation raw data
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter policy escalation records
    
    Returns:
        Tuple: (policy_escalation_percentage, escalation_count) or (0.0, 0) if no data
    """
    print(f"📊 CALCULATING POLICY ESCALATION PERCENTAGE...")
    
    try:
        # Query policy escalation raw data table for target date, department, and policy_escalation prompt only
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS,
            CONVERSATION_ID
        FROM LLM_EVAL.PUBLIC.POLICY_ESCALATION_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'policy_escalation'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No POLICY_ESCALATION_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        print(f"   📊 Found {len(results_df)} policy escalation records for {department_name} on {target_date}")
        
        print(f"📊 Creating policy escalation summary table...")
        summary_success, summary_stats = create_policy_escalation_summary_report(session, results_df, department_name, target_date)
        
        if summary_success:
            print(f"   ✅ Policy escalation summary table created successfully")
            print(f"       Total conversations analyzed: {summary_stats.get('total_conversations', 0)}")
            print(f"       Valid outputs: {summary_stats.get('valid_outputs', 0)}")
            print(f"       Customer escalations (true): {summary_stats.get('customer_escalation_true_count', 0)}")
            print(f"       Parsing errors: {summary_stats.get('parsing_errors', 0)}")
            print(f"       Overall policy escalation percentage: {summary_stats.get('percentage', 0):.1f}%")
        else:
            print(f"   ⚠️  Failed to create policy escalation summary table: {summary_stats.get('error', 'Unknown error')}")
        
        
        chats_analyzed = len(results_df)
        parsed_conversations = 0
        customer_escalation_true_count = 0
        valid_outputs = 0
        parsing_errors = 0
        
        # Process each record
        for _, row in results_df.iterrows():
            try:
                conversation_id = str(row['CONVERSATION_ID'])
                llm_response = row['LLM_RESPONSE']
                if not isinstance(llm_response, str) or not llm_response.strip():
                    continue
                
                # Parse the JSON output
                parsed_result = safe_json_parse(llm_response)
                
                if parsed_result and isinstance(parsed_result, dict):
                    parsed_conversations += 1
                    valid_outputs += 1
                    customer_escalation = parse_boolean_flexible(parsed_result.get('CustomerEscalation', False))
                    if customer_escalation is True:
                        customer_escalation_true_count += 1
                else:
                    parsing_errors += 1
                    print(f"   ⚠️  Invalid JSON output for conversation: {conversation_id}")
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"   ⚠️  Failed to parse policy escalation data: {str(e)}")
                parsing_errors += 1
                continue
        
        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for policy escalation analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0, empty_stats
        
        # Calculate policy escalation percentage: Customer escalations / Total conversations * 100
        percentage = (customer_escalation_true_count / parsed_conversations) * 100
        
        print(f"   📈 Policy Escalation Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Valid outputs: {valid_outputs}")
        print(f"   Customer escalations (true): {customer_escalation_true_count}")
        print(f"   Parsing errors: {parsing_errors}")
        print(f"   Overall policy escalation percentage: {percentage:.1f}%")
        
        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage, 1), customer_escalation_true_count, failure_stats
        
    except Exception as e:
        error_details = format_error_details(e, "POLICY ESCALATION PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate policy escalation percentage: {str(e)}")
        print(error_details)
        return 0.0, 0

def calculate_transer_escalation_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate transfer escalation percentage from SALES_TRANSFER_ESCALATION_RAW_DATA.

    Returns:
      Tuple: (transfer_escalation_percentage, transfer_escalation_count, analysis_summary_json)

    Formula:
      ( number of chats where transfers_escalation = true / number of chats where transfer_detected = true ) * 100
    """
    print(f"📊 CALCULATING TRANSFER ESCALATION PERCENTAGE...")

    try:
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS,
            CONVERSATION_ID
        FROM LLM_EVAL.PUBLIC.TRANSFER_ESCALATION_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROMPT_TYPE = 'sales_transfer_escalation'
          AND PROCESSING_STATUS = 'COMPLETED'
        """

        results_df = session.sql(query).to_pandas()

        if results_df.empty:
            print(f"   ℹ️  No SALES_TRANSFER_ESCALATION_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats

        print(f"   📊 Found {len(results_df)} transfer escalation records for {department_name} on {target_date}")

        chats_analyzed = len(results_df)
        parsed_conversations = 0
        denominator_transfer_detected = 0
        transfers_escalation_true_count = 0

        for _, row in results_df.iterrows():
            try:
                llm_response = row['LLM_RESPONSE']

                parsed = None
                if isinstance(llm_response, dict):
                    parsed = llm_response
                elif isinstance(llm_response, str) and llm_response.strip():
                    parsed = safe_json_parse(llm_response)
                else:
                    continue

                if isinstance(parsed, dict):
                    parsed_conversations += 1
                    transfer_detected = parse_boolean_flexible(parsed.get('transfer_detected'))
                    transfers_escalation = parse_boolean_flexible(parsed.get('transfers_escalation'))

                    if transfer_detected is True:
                        denominator_transfer_detected += 1
                        if transfers_escalation is True:
                            transfers_escalation_true_count += 1
            except Exception as e:
                print(f"   ⚠️  Failed to process transfer escalation row: {str(e)}")
                continue

        if denominator_transfer_detected == 0:
            print("   ⚠️  No chats with transfer_detected=true; cannot compute transfer escalation percentage")
            failure_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": parsed_conversations,
                "chats_failed": chats_analyzed - parsed_conversations,
                "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0, failure_stats

        percentage_a = (transfers_escalation_true_count / denominator_transfer_detected) * 100
        percentage_b = (transfers_escalation_true_count / parsed_conversations) * 100

        print(f"   📈 Transfer Escalation Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Successfully parsed: {parsed_conversations}")
        print(f"   transfer_detected=true: {denominator_transfer_detected}")
        print(f"   transfers_escalation=true: {transfers_escalation_true_count}")
        print(f"   Transfer Escalation Percentage A: {percentage_a:.1f}%")
        print(f"   Transfer Escalation Percentage B: {percentage_b:.1f}%")

        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage_a, 1), round(percentage_b, 1), transfers_escalation_true_count, failure_stats

    except Exception as e:
        error_details = format_error_details(e, "TRANSFER ESCALATION PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate transfer escalation percentage: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, empty_stats

def calculate_transer_known_flow_percentage(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate transfer escalation percentage from SALES_TRANSFER_ESCALATION_RAW_DATA.

    Returns:
      Tuple: (transfer_escalation_percentage, transfer_escalation_count, analysis_summary_json)

    Formula:
      ( number of chats where transfers_escalation = true / number of chats where transfer_detected = true ) * 100
    """
    print(f"📊 CALCULATING TRANSFER ESCALATION PERCENTAGE...")

    try:
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS,
            CONVERSATION_ID
        FROM LLM_EVAL.PUBLIC.TRANSFER_KNOWN_FLOW_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROMPT_TYPE = 'sales_transfer_known_flow'
          AND PROCESSING_STATUS = 'COMPLETED'
        """

        results_df = session.sql(query).to_pandas()

        if results_df.empty:
            print(f"   ℹ️  No SALES_TRANSFER_KNOWN_FLOW_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats

        print(f"   📊 Found {len(results_df)} transfer known flow records for {department_name} on {target_date}")

        chats_analyzed = len(results_df)
        parsed_conversations = 0
        denominator_transfer_detected = 0
        transfers_known_flow_true_count = 0

        for _, row in results_df.iterrows():
            try:
                llm_response = row['LLM_RESPONSE']

                parsed = None
                if isinstance(llm_response, dict):
                    parsed = llm_response
                elif isinstance(llm_response, str) and llm_response.strip():
                    parsed = safe_json_parse(llm_response)
                else:
                    continue

                if isinstance(parsed, dict):
                    parsed_conversations += 1
                    transfer_detected = parse_boolean_flexible(parsed.get('transfer_detected'))
                    transfers_known_flow = parse_boolean_flexible(parsed.get('transfers_known_flow'))

                    if transfer_detected is True:
                        denominator_transfer_detected += 1
                        if transfers_known_flow is True:
                            transfers_known_flow_true_count += 1
            except Exception as e:
                print(f"   ⚠️  Failed to process transfer escalation row: {str(e)}")
                continue

        if denominator_transfer_detected == 0:
            print("   ⚠️  No chats with transfer_detected=true; cannot compute transfer escalation percentage")
            failure_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": parsed_conversations,
                "chats_failed": chats_analyzed - parsed_conversations,
                "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0, failure_stats

        percentage_a = (1 - (transfers_known_flow_true_count / denominator_transfer_detected)) * 100
        percentage_b = ((denominator_transfer_detected - transfers_known_flow_true_count) / parsed_conversations) * 100

        print(f"   📈 Transfer Escalation Analysis Results:")
        print(f"   Total conversations analyzed: {chats_analyzed}")
        print(f"   Successfully parsed: {parsed_conversations}")
        print(f"   transfer_detected=true: {denominator_transfer_detected}")
        print(f"   transfers_known_flow=true: {transfers_known_flow_true_count}")
        print(f"   Transfer Escalation Percentage A: {percentage_a:.1f}%")
        print(f"   Transfer Escalation Percentage B: {percentage_b:.1f}%")

        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage_a, 1), round(percentage_b, 1), transfers_known_flow_true_count, failure_stats

    except Exception as e:
        error_details = format_error_details(e, "TRANSFER KNOWN FLOW PERCENTAGE CALCULATION")
        print(f"   ❌ Failed to calculate transfer known flow percentage: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, empty_stats


def calculate_cc_sales_policy_violation_metrics(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate policy violation metrics for CC Sales from POLICY_VIOLATION_RAW_DATA.

    Expected LLM_RESPONSE structure:
    {
      "missing_policy": true|false,
      "unclear_policy": true|false,
      "violation_types": [],
      "style_notes": [],
      "evidence": [],
      "confidence": 0.9,
      "abstain": true|false
    }

    Returns (in order):
      - float: MISSING_POLICY_PERCENTAGE (over analyzed)
      - int: MISSING_POLICY_COUNT
      - float: UNCLEAR_POLICY_PERCENTAGE (over analyzed)
      - int: UNCLEAR_POLICY_COUNT
      - str: analysis summary JSON {chats_analyzed, chats_parsed, chats_failed, failure_percentage}
    """
    print(f"📊 CALCULATING CC SALES POLICY VIOLATION METRICS...")
    try:
        query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.POLICY_VIOLATION_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROMPT_TYPE = 'policy_violation'
          AND PROCESSING_STATUS = 'COMPLETED'
          AND LLM_RESPONSE IS NOT NULL
          AND LLM_RESPONSE != ''
        """
        results_df = session.sql(query).to_pandas()

        if results_df.empty:
            print(f"   ℹ️  No POLICY_VIOLATION_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, 0.0, 0, empty_stats

        total_chats_analyzed = len(results_df)
        parsed_conversations = 0
        missing_policy_count = 0
        unclear_policy_count = 0

        for _, row in results_df.iterrows():
            try:
                llm_response = row['LLM_RESPONSE']
                parsed = None
                if isinstance(llm_response, dict):
                    parsed = llm_response
                elif isinstance(llm_response, str) and llm_response.strip():
                    parsed = safe_json_parse(llm_response)

                if isinstance(parsed, dict):
                    parsed_conversations += 1
                    if parse_boolean_flexible(parsed.get('missing_policy')) is True:
                        missing_policy_count += 1
                    if parse_boolean_flexible(parsed.get('unclear_policy')) is True:
                        unclear_policy_count += 1
            except Exception:
                continue

        missing_pct = (missing_policy_count / parsed_conversations * 100.0) if parsed_conversations > 0 else 0.0
        unclear_pct = (unclear_policy_count / parsed_conversations * 100.0) if parsed_conversations > 0 else 0.0

        failure_stats = json.dumps({
            "chats_analyzed": int(total_chats_analyzed),
            "chats_parsed": int(parsed_conversations),
            "chats_failed": int(total_chats_analyzed - parsed_conversations),
            "failure_percentage": round(((total_chats_analyzed - parsed_conversations) / total_chats_analyzed) * 100, 1) if total_chats_analyzed > 0 else 0.0
        }, indent=2)

        print(f"   📈 Missing Policy: {missing_policy_count}/{parsed_conversations} → {missing_pct:.1f}%")
        print(f"   📈 Unclear Policy: {unclear_policy_count}/{parsed_conversations} → {unclear_pct:.1f}%")

        return round(missing_pct, 1), int(missing_policy_count), round(unclear_pct, 1), int(unclear_policy_count), failure_stats

    except Exception as e:
        error_details = format_error_details(e, "CC SALES POLICY VIOLATION METRICS CALCULATION")
        print(f"   ❌ Failed to calculate CC Sales policy violation metrics: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, 0.0, 0, empty_stats

def calculate_unclear_policy_metrics(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate Unclear Policy metrics from UNCLEAR_POLICY_RAW_DATA.

    LLM_RESPONSE sample structure:
    {
      "confusingPolicy": "Yes|No|True|False",
      "Category": "...",
      "PolicyText": "...",
      "Justification": "..."
    }

    Formula:
      (count(confusingPolicy == Yes) / total_chats_analyzed) * 100

    Returns (in order):
      - float: unclear policy percentage (rounded to 1)
      - int: unclear/confusing policy count
      - str: analysis summary JSON {chats_analyzed, chats_parsed, chats_failed, failure_percentage}
    """
    print(f"📊 CALCULATING UNCLEAR POLICY METRICS...")
    try:
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.UNCLEAR_POLICY_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROMPT_TYPE = 'unclear_policy'
          AND PROCESSING_STATUS = 'COMPLETED'
          AND LLM_RESPONSE IS NOT NULL
          AND LLM_RESPONSE != ''
        """
        results_df = session.sql(query).to_pandas()

        if results_df.empty:
            print(f"   ℹ️  No UNCLEAR_POLICY_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats

        print(f"   📊 Found {len(results_df)} unclear policy records for {department_name} on {target_date}")

        chats_analyzed = len(results_df)
        parsed_conversations = 0
        unclear_policy_count = 0

        for _, row in results_df.iterrows():
            try:
                llm_response = row['LLM_RESPONSE']
                parsed = None
                if isinstance(llm_response, dict):
                    parsed = llm_response
                elif isinstance(llm_response, str) and llm_response.strip():
                    parsed = safe_json_parse(llm_response)

                if isinstance(parsed, dict):
                    parsed_conversations += 1
                    cp_value = parsed.get('confusingPolicy')
                    is_confusing = parse_boolean_flexible(cp_value) is True
                    if is_confusing:
                        unclear_policy_count += 1
            except Exception:
                # skip malformed rows
                continue

        # Denominator is total chats analyzed (not just parsed)
        percentage = (unclear_policy_count / parsed_conversations * 100.0) if parsed_conversations > 0 else 0.0

        print(f"   📈 Unclear Policy Results: {unclear_policy_count}/{parsed_conversations} → {percentage:.1f}%")

        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage, 1), int(unclear_policy_count), failure_stats

    except Exception as e:
        error_details = format_error_details(e, "UNCLEAR POLICY METRICS CALCULATION")
        print(f"   ❌ Failed to calculate unclear policy metrics: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, empty_stats

def analyze_doctors_categorizing_data_snowflake(session: snowpark.Session, department_name: str, target_date):
    """
    Analyze doctors categorizing prompt results from Snowflake table and return parsed DataFrame
    
    Args:
        session: Snowflake session
        department_name: Name of the department to analyze
        target_date: Target date to filter doctors categorizing records
    
    Returns:
        DataFrame with parsed doctors categorizing results or None if no data
    """
    print(f"📊 Analyzing doctors categorizing results from Snowflake for {department_name} on date: {target_date}")
    
    try:
        # Query DOCTORS_CATEGORIZING_RAW_DATA table for target date, department, and categorizing prompt only
        query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.DOCTORS_CATEGORIZING_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'doctors_categorizing'
        AND PROCESSING_STATUS = 'COMPLETED'
        """
        
        results_df = session.sql(query).to_pandas()
        
        if results_df.empty:
            print(f"   ℹ️  No DOCTORS_CATEGORIZING_RAW_DATA data found for {department_name} on {target_date}")
            return None
        
        print(f"   📈 Loaded {len(results_df)} conversations from Snowflake")
        
        # Parse JSON outputs
        parsed_results = []
        parse_errors = 0
        
        for idx, row in results_df.iterrows():
            llm_output = row['LLM_RESPONSE']
            parsed = safe_json_parse(llm_output)
            
            if parsed:
                # Extract categories from the array, handling single values too
                categories = parsed.get('category', [])
                if isinstance(categories, str):
                    categories = [categories]
                elif not isinstance(categories, list):
                    categories = ['null']
                
                # Get the primary category (first one, or 'null' if empty)
                primary_category = categories[0] if categories else 'null'
                
                parsed_results.append({
                    'chat_id': row['CONVERSATION_ID'],
                    'department': row['DEPARTMENT'],
                    'category': primary_category,
                    'all_categories': categories,
                    'clinic_recommendation': parsed.get('Clinic Recommendation', 'No'),
                    'otc_medication_advice': parsed.get('OTC Medication Advice', 'No'),
                    'reasoning': parsed.get('reasoning', ''),
                    'original_output': llm_output
                })
            else:
                parse_errors += 1
                # Still add to results for counting
                parsed_results.append({
                    'chat_id': row['CONVERSATION_ID'],
                    'department': row['DEPARTMENT'],
                    'category': 'Parse_Error',
                    'all_categories': ['Parse_Error'],
                    'clinic_recommendation': 'No',
                    'otc_medication_advice': 'No',
                    'reasoning': '',
                    'original_output': llm_output
                })
        
        print(f"   ✅ Successfully parsed: {len(parsed_results) - parse_errors}/{len(results_df)} conversations")
        if parse_errors > 0:
            print(f"   ⚠️  Parse errors: {parse_errors}")
        
        # Create results DataFrame
        results_df = pd.DataFrame(parsed_results)
        
        # Count categories
        category_counts = Counter(results_df['category'])
        clinic_rec_counts = Counter(results_df['clinic_recommendation'])
        otc_counts = Counter(results_df['otc_medication_advice'])
        
        print(f"\n   📋 Category Breakdown:")
        for category, count in category_counts.most_common():
            percentage = (count / len(results_df)) * 100
            print(f"     {category}: {count} ({percentage:.1f}%)")
        
        print(f"\n   🏥 Clinic Recommendation: {clinic_rec_counts}")
        print(f"   💊 OTC Medication Advice: {otc_counts}")
        
        return results_df

    except Exception as e:
        error_details = format_error_details(e, "DOCTORS CATEGORIZING DATA ANALYSIS")
        print(f"   ❌ Failed to analyze doctors categorizing data: {str(e)}")
        print(error_details)
        return None

def create_doctors_categorizing_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Create doctors categorizing summary report and store in Snowflake table
    
    Args:
        session: Snowflake session
        parsed_df: DataFrame with parsed doctors categorizing results
        department_name: Name of the department being analyzed
        target_date: Target date for analysis
    
    Returns:
        Success status and summary statistics
    """
    print(f"📊 Creating doctors categorizing summary report for {department_name} on {target_date}...")
    
    try:
        # Step 1: Analyze doctors categorizing data from Snowflake
        parsed_df = analyze_doctors_categorizing_data_snowflake(session, department_name, target_date)
        
        if parsed_df is None or parsed_df.empty:
            print(f"   ℹ️  No doctors categorizing data found for {department_name} on {target_date}")
            return True, {'total_conversations': 0}
        
        # Get all unique categories from all chats
        all_categories = set(parsed_df['category'].unique())
        
        # Calculate overall statistics
        total_chats = len(parsed_df)
        total_clinic_rec = len(parsed_df[parsed_df['clinic_recommendation'] == 'Yes'])
        total_otc = len(parsed_df[parsed_df['otc_medication_advice'] == 'Yes'])
        
        pct_overall_clinic_rec = (total_clinic_rec / total_chats * 100) if total_chats > 0 else 0
        pct_overall_otc = (total_otc / total_chats * 100) if total_chats > 0 else 0
        
        summary_data = []
        
        # Process each category
        for category in sorted(all_categories):
            if category in ['Parse_Error', 'null', '']:
                continue  # Skip invalid categories
            
            # Find all chats with this category
            category_data = parsed_df[parsed_df['category'] == category]
            category_count = len(category_data)
            
            if category_count == 0:
                continue
            
            # Count clinic recommendations and OTC advice in this category
            clinic_rec_yes = len(category_data[category_data['clinic_recommendation'] == 'Yes'])
            otc_yes = len(category_data[category_data['otc_medication_advice'] == 'Yes'])
            
            # Calculate percentages
            category_pct = (category_count / total_chats * 100) if total_chats > 0 else 0
            clinic_rec_pct = (clinic_rec_yes / category_count * 100) if category_count > 0 else 0
            otc_pct = (otc_yes / category_count * 100) if category_count > 0 else 0
            
            summary_data.append({
                'CATEGORY': category,
                'COUNT': category_count,
                'CATEGORY_PCT': round(category_pct, 2),
                'CLINIC_RECOMMENDATION_COUNT': clinic_rec_yes,
                'CLINIC_RECOMMENDATION_PCT': round(clinic_rec_pct, 2),
                'OTC_MEDICATION_COUNT': otc_yes,
                'OTC_MEDICATION_PCT': round(otc_pct, 2),
                'OVERALL_CLINIC_REC_PCT': round(pct_overall_clinic_rec, 2),
                'OVERALL_OTC_PCT': round(pct_overall_otc, 2)
            })
        
        # Create summary DataFrame
        summary_df = pd.DataFrame(summary_data)
        
        # Sort by Count (descending)
        if len(summary_df) > 0:
            summary_df = summary_df.sort_values('COUNT', ascending=False)
        
        if summary_df.empty:
            print(f"   ⚠️  No valid categories found for doctors categorizing summary")
            return True
        
        # Import the insert function from processor module
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        
        # Insert summary data into doctors categorizing summary table
        dynamic_columns = list(summary_df.columns)
        
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='DOCTORS_CATEGORIZING_SUMMARY',
            department=department_name,  # Use specific department
            target_date=target_date,
            dataframe=summary_df,
            columns=dynamic_columns
        )
        
        if not insert_success or insert_success.get('status') != 'success':
            print(f"   ❌ Failed to insert doctors categorizing summary data")
            return False
        
        # Show quick summary
        print(f"\n   📊 Doctors Categorizing Summary Report:")
        print(f"   Total conversations analyzed: {total_chats}")
        print(f"   Total categories found: {len(summary_df)}")
        print(f"   Overall clinic recommendations: {total_clinic_rec} ({pct_overall_clinic_rec:.1f}%)")
        print(f"   Overall OTC medication advice: {total_otc} ({pct_overall_otc:.1f}%)")
        
        # Show top 5 categories by count
        if len(summary_df) > 0:
            print(f"\n   Top categories by volume:")
            for i, row in summary_df.head(5).iterrows():
                print(f"     {i+1}. {row['CATEGORY']}: {row['COUNT']} chats ({row['CATEGORY_PCT']:.1f}%)")
                print(f"         Clinic Rec: {row['CLINIC_RECOMMENDATION_COUNT']} ({row['CLINIC_RECOMMENDATION_PCT']:.1f}%), OTC: {row['OTC_MEDICATION_COUNT']} ({row['OTC_MEDICATION_PCT']:.1f}%)")
        
        
        
        return True
        
    except Exception as e:
        error_details = format_error_details(e, "DOCTORS CATEGORIZING SUMMARY REPORT")
        print(f"   ❌ Failed to create doctors categorizing summary report: {str(e)}")
        print(error_details)
        return False

def create_policy_escalation_summary_report(session: snowpark.Session, results_df, department_name: str, target_date):
    """
    Create policy escalation frequency summary report and store in Snowflake table
    
    Args:
        session: Snowflake session
        department_name: Name of the department being analyzed
        target_date: Target date for analysis
    
    Returns:
        Success status and summary statistics
    """
    print(f"📊 Creating policy escalation frequency summary for {department_name} on {target_date}...")
    
    try:
        
        # Extract policies from LLM outputs
        policies = []
        total_conversations = len(results_df)
        valid_jsons = 0
        escalations_found = 0
        parsing_errors = 0
        
        for _, row in results_df.iterrows():
            try:
                conversation_id = str(row['CONVERSATION_ID'])
                llm_response = row['LLM_RESPONSE']
                
                if not isinstance(llm_response, str) or not llm_response.strip():
                    continue
                
                # Parse JSON output
                parsed_result = safe_json_parse(llm_response)
                
                if parsed_result and isinstance(parsed_result, dict):
                    valid_jsons += 1
                    
                    # Get PolicyToCauseEscalation and robustly parse CustomerEscalation as boolean
                    policy = parsed_result.get('PolicyToCauseEscalation', '')
                    raw_customer_escalation = parsed_result.get('CustomerEscalation', None)

                    customer_escalation = None
                    if isinstance(raw_customer_escalation, bool):
                        customer_escalation = raw_customer_escalation
                    elif isinstance(raw_customer_escalation, (int, float)):
                        if raw_customer_escalation in [1, 1.0]:
                            customer_escalation = True
                        elif raw_customer_escalation in [0, 0.0]:
                            customer_escalation = False
                    elif isinstance(raw_customer_escalation, str):
                        val_norm = raw_customer_escalation.strip().lower()
                        if val_norm in {'true', 't', 'yes', 'y', '1'}:
                            customer_escalation = True
                        elif val_norm in {'false', 'f', 'no', 'n', '0'}:
                            customer_escalation = False
                    
                    # Only count non-N/A policies as escalations OR cases where CustomerEscalation is true while policy is N/A
                    if (policy and policy != 'N/A' and policy.strip() != ''):
                        escalations_found += 1
                        # Clean up policy text for better readability
                        clean_policy = policy.strip()
                        policies.append(clean_policy)
                else:
                    parsing_errors += 1
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"   ⚠️  Failed to parse policy escalation data for conversation {conversation_id}: {str(e)}")
                parsing_errors += 1
                continue
        
        if not policies:
            print("   ⚠️  No policy escalations found (all PolicyToCauseEscalation were 'N/A')")
            return True, {'total_conversations': total_conversations, 'escalations_found': 0}
        
        # Count policy frequencies
        policy_counts = Counter(policies)
        
        # Create frequency table
        frequency_data = []
        for policy, count in policy_counts.most_common():
            frequency_data.append({
                'POLICY': policy,
                'COUNT': count,
                'PERCENTAGE': round((count / escalations_found * 100), 2),
                'TOTAL_ESCALATIONS': escalations_found,
                'TOTAL_CONVERSATIONS': total_conversations
            })
        
        frequency_df = pd.DataFrame(frequency_data)
        
        if frequency_df.empty:
            print(f"   ⚠️  No valid policies found for summary")
            return True, {'total_conversations': total_conversations, 'escalations_found': 0}
        
        # Import the insert function from processor module
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        
        # Insert summary data into policy escalation summary table
        dynamic_columns = list(frequency_df.columns)
        
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='POLICY_ESCALATION_SUMMARY',
            department=department_name,  # Use specific department
            target_date=target_date,
            dataframe=frequency_df,
            columns=dynamic_columns
        )
        
        if not insert_success or insert_success.get('status') != 'success':
            print(f"   ❌ Failed to insert policy escalation summary data")
            return False, {'error': 'Failed to insert summary data'}
        
        # Show quick summary
        print(f"\n   📊 Policy Escalation Frequency Summary:")
        print(f"   Total conversations analyzed: {total_conversations}")
        print(f"   Valid JSON outputs: {valid_jsons}")
        print(f"   Policy escalations found: {escalations_found}")
        print(f"   Unique policies causing escalation: {len(policy_counts)}")
        print(f"   Parsing errors: {parsing_errors}")
        
        # Show top 5 policies by frequency
        if len(frequency_df) > 0:
            print(f"\n   Top policies by frequency:")
            for i, row in frequency_df.head(5).iterrows():
                policy_text = row['POLICY']
                # Truncate long policies for display
                if len(policy_text) > 80:
                    policy_text = policy_text[:80] + "..."
                print(f"     {i+1}. {policy_text}")
                print(f"         Count: {row['COUNT']}, Percentage: {row['PERCENTAGE']:.1f}%")
        
        summary_stats = {
            'total_conversations': total_conversations,
            'valid_jsons': valid_jsons,
            'escalations_found': escalations_found,
            'unique_policies': len(policy_counts),
            'parsing_errors': parsing_errors,
            'rows_inserted': len(frequency_df)
        }
        
        return True, summary_stats
        
    except Exception as e:
        error_details = format_error_details(e, "POLICY ESCALATION FREQUENCY SUMMARY")
        print(f"   ❌ Failed to create policy escalation frequency summary: {str(e)}")
        print(error_details)
        return False, {'error': str(e)}
   
def create_system_prompt_token_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Batch-calculate system prompt token counts for conversations analyzed under policy_escalation
    and insert rows into SYSTEM_PROMPT_TOKENS_RAW_DATA.

    Columns inserted (plus essential DATE/DEPARTMENT/TIMESTAMP):
      - CONVERSATION_ID
      - GPT_AGENT_NAME
      - TOKENIZER_MODEL (constant 'gpt-4o-mini')
      - NUMBER_OF_TOKENS (numeric)

    Returns:
      float: average NUMBER_OF_TOKENS for the batch (0.0 if none)
    """
    print(f"📊 Creating system prompt token summary report for {department_name} on {target_date}...")
    try:
        # Fetch department's GPT agent name to disambiguate prompt mapping
        from snowflake_llm_config import get_snowflake_llm_departments_config
        departments_config = get_snowflake_llm_departments_config()
        llm_prompts = departments_config.get(department_name, {}).get('llm_prompts', {})
        if 'policy_escalation' in llm_prompts:
            table_name = llm_prompts['policy_escalation'].get('table_name', 'POLICY_ESCALATION_RAW_DATA')
            prompt_type = llm_prompts['policy_escalation'].get('prompt_type', 'policy_escalation')
        else:
            table_name = 'POLICY_VIOLATION_RAW_DATA'
            prompt_type = 'policy_violation'

        print(f"   🔄 Fetching system prompt token counts for {department_name} on {target_date} from {table_name}...")
        # Build a single SQL to:
        # 1) Grab conversation ids and execution ids from POLICY_ESCALATION_RAW_DATA for given dept/date
        # 2) Resolve bot system prompts via GET_N8N_SYSTEM_PROMPT(EXECUTION_ID)
        # 3) Count tokens using openai_count_system_tokens for 'gpt-4o-mini'
        sql_query = f"""
        WITH candidates AS (
            SELECT DISTINCT CONVERSATION_ID, EXECUTION_ID
            FROM LLM_EVAL.PUBLIC.{table_name}
            WHERE DATE(DATE) = DATE('{target_date}')
              AND DEPARTMENT = '{department_name}'
              AND PROMPT_TYPE = '{prompt_type}'
              AND PROCESSING_STATUS = 'COMPLETED'
        ),
        resolved_prompts AS (
            SELECT 
                CONVERSATION_ID,
                COALESCE(GET_N8N_SYSTEM_PROMPT(EXECUTION_ID), GET_ERP_SYSTEM_PROMPT(CONVERSATION_ID)) AS bot_system_prompt
            FROM candidates
        ),
        token_counts AS (
            SELECT 
                CONVERSATION_ID,
                bot_system_prompt,
                'gpt-4o-mini' AS TOKENIZER_MODEL,
                openai_count_system_tokens(bot_system_prompt, 'gpt-4o-mini') AS NUMBER_OF_TOKENS
            FROM resolved_prompts
            WHERE bot_system_prompt IS NOT NULL
        )
        SELECT CONVERSATION_ID, LEFT(bot_system_prompt, 500) as "SYSTEM_PROMPT_SNAPSHOT", TOKENIZER_MODEL, NUMBER_OF_TOKENS
        FROM token_counts
        """

        print("   🔄 Executing token counting batch SQL...")
        tokens_df = session.sql(sql_query).to_pandas()

        if tokens_df.empty:
            print("   ℹ️  No token rows generated (missing mappings or no candidates)")
            return 0.0

        # Insert into SYSTEM_PROMPT_TOKENS_RAW_DATA using existing helper
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        dynamic_columns = ['CONVERSATION_ID', 'SYSTEM_PROMPT_SNAPSHOT', 'TOKENIZER_MODEL', 'NUMBER_OF_TOKENS']
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='SYSTEM_PROMPT_TOKENS_RAW_DATA',
            department=department_name,
            target_date=target_date,
            dataframe=tokens_df[dynamic_columns],
            columns=dynamic_columns
        )

        if not insert_success or insert_success.get('status') != 'success':
            print("   ❌ Failed to insert system prompt token rows")
            return 0.0

        avg_tokens = float(tokens_df['NUMBER_OF_TOKENS'].astype(float).mean())
        print(f"   ✅ Token rows inserted: {len(tokens_df)}, average tokens: {avg_tokens:.2f}")
        return round(avg_tokens, 2)

    except Exception as e:
        error_details = format_error_details(e, "SYSTEM PROMPT TOKEN SUMMARY")
        print(f"   ❌ Failed to create system prompt token summary report: {str(e)}")
        print(error_details)
        return 0.0

def create_loss_interest_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Create loss interest summary report grouped by recruitment stage (category) and store in Snowflake.

    Per category (from category_last_skill_map), output one row per (MAIN_REASON, SUB_REASON) with:
      - RECRUITMENT_STAGE (category)
      - MAIN_REASON
      - SUB_REASON
      - MAIN_REASON_COUNT (within the same category)
      - SUB_REASON_COUNT (within the same category)
      - SUB_REASON_PCT = SUB_REASON_COUNT / MAIN_REASON_COUNT * 100

    Returns:
      bool: True if insertion completed successfully (or no data to insert), False otherwise
    """
    print(f"📊 Creating loss interest summary report for {department_name} on {target_date}...")
    
    try:

        category_last_skill_map = {
            'Photo Submission Outside UAE': ['Filipina_Outside_Pending_Facephoto'],
            'Passport Submission Outside UAE': ['Filipina_Outside_Pending_Passport'],
            'Joining Date Outside UAE': ['Filipina_Outside_UAE_Pending_Joining_Date'],
            'Active Visa Submission Philippines': ['Filipina_in_PHl_Pending_valid_visa'],
            'Passport Submission (Photo) Philippines': ['Filipina_in_PHL_Pending_Passport'],
            'Photo Submission (Photo) Philippines': ['Filipina_in_PHl_Pending_Facephoto'],
            'OEC Philippines': ['Filipina_in_PHl_Pending_OEC_From_maid', 'Filipina_in_PHl_Pending_OEC_From_Company'],
        }

        # Step 1: Load raw data from LOSS_INTEREST_RAW_DATA
        raw_query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS,
            LAST_SKILL
        FROM LLM_EVAL.PUBLIC.LOSS_INTEREST_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'loss_interest'
        AND PROCESSING_STATUS = 'COMPLETED'
        AND LLM_RESPONSE IS NOT NULL
        AND LLM_RESPONSE != ''
        """
        raw_df = session.sql(raw_query).to_pandas()
        
        if raw_df.empty:
            print(f"   ℹ️  No LOSS_INTEREST_RAW_DATA data found for {department_name} on {target_date}")
            return True
        
        print(f"   📈 Loaded {len(raw_df)} loss interest rows from Snowflake")
        
        # Step 2: Parse JSON and collect reasons, grouped by recruitment stage via LAST_SKILL
        # Build skill -> categories reverse map for quick lookup
        skill_to_categories = {}
        for category, skills in category_last_skill_map.items():
            for s in skills:
                skill_to_categories.setdefault(str(s), set()).add(category)

        # Counters scoped per category
        main_counter_by_cat = Counter()         # key: (category, main_reason)
        pair_counter_by_cat = Counter()         # key: (category, main_reason, sub_reason)

        parsed_count = 0
        parse_errors = 0

        for _, row in raw_df.iterrows():
            llm_output = row['LLM_RESPONSE']
            last_skill = str(row.get('LAST_SKILL', '')).strip()
            parsed = safe_json_parse(llm_output)

            if not isinstance(parsed, dict):
                parse_errors += 1
                continue

            main_reason = str(parsed.get('Reason Category') or 'N/A')
            sub_reason = str(parsed.get('Reason Subcategory') or 'N/A')

            # Determine which categories this row contributes to (based on LAST_SKILL)
            matched_categories = skill_to_categories.get(last_skill, set())
            if not matched_categories:
                # Skip rows that do not map to any configured recruitment stage
                continue

            parsed_count += 1
            for category in matched_categories:
                main_counter_by_cat[(category, main_reason)] += 1
                pair_counter_by_cat[(category, main_reason, sub_reason)] += 1

        if parsed_count == 0 and not pair_counter_by_cat:
            print("   ⚠️  No valid JSON rows mapped to recruitment stages for loss interest")
            return True

        # Step 3: Build summary rows per category
        # Precompute total MAIN_REASON counts per category to derive MAIN_REASON_PCT within category
        total_main_per_category = {}
        for (cat_key, main_reason_key), cnt in main_counter_by_cat.items():
            total_main_per_category[cat_key] = total_main_per_category.get(cat_key, 0) + int(cnt)

        summary_rows = []
        for (category, main_reason, sub_reason), sub_count in pair_counter_by_cat.items():
            main_count = int(main_counter_by_cat.get((category, main_reason), 0))
            pct = round((sub_count / main_count) * 100, 2) if main_count > 0 else 0.0
            cat_total_main = int(total_main_per_category.get(category, 0))
            main_reason_pct = round((main_count / cat_total_main) * 100, 2) if cat_total_main > 0 else 0.0
            summary_rows.append({
                'RECRUITMENT_STAGE': category,
                'MAIN_REASON': main_reason,
                'SUB_REASON': sub_reason,
                'MAIN_REASON_COUNT': int(main_count),
                'MAIN_REASON_PCT': main_reason_pct,
                'SUB_REASON_COUNT': int(sub_count),
                'SUB_REASON_PCT': pct
            })

        
        
        if not summary_rows:
            print("   ⚠️  No summary rows generated for loss interest")
            return True
        
        summary_df = pd.DataFrame(summary_rows)
        # Sort rows by MAIN_REASON for readability
        summary_df = summary_df.sort_values(by=['RECRUITMENT_STAGE', 'MAIN_REASON']).reset_index(drop=True)
        
        # Step 4: Insert into LOSS_INTEREST_SUMMARY
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='LOSS_INTEREST_SUMMARY',
            department=department_name,
            target_date=target_date,
            dataframe=summary_df,
            columns=list(summary_df.columns)
        )
        
        if not insert_success or insert_success.get('status') != 'success':
            print("   ❌ Failed to insert loss interest summary data")
            return False
        
        print(f"   ✅ Loss interest summary inserted: {len(summary_df)} rows")
        return True
        
    except Exception as e:
        error_details = format_error_details(e, "LOSS INTEREST SUMMARY REPORT")
        print(f"   ❌ Failed to create loss interest summary report: {str(e)}")
        print(error_details)
        return False

def create_clinic_reasons_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Create clinic reasons categories summary and store in Snowflake table.

    Output table columns (dynamic):
      - CATEGORY_NAME
      - NUMBER_OF_CHATS (number of distinct conversations where this category appeared)

    Returns:
      bool: True if insertion completed successfully (or no data to insert), False otherwise
    """
    print(f"📊 Creating clinic reasons summary report for {department_name} on {target_date}...")

    try:
        # Step 1: Load raw data from CLINIC_RECOMMENDATION_REASON_RAW_DATA
        raw_query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.CLINIC_RECOMMENDATION_REASON_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
        AND DEPARTMENT = '{department_name}'
        AND PROMPT_TYPE = 'clinic_recommendation_reason'
        AND PROCESSING_STATUS = 'COMPLETED'
        AND LLM_RESPONSE IS NOT NULL
        AND LLM_RESPONSE != ''
        """
        raw_df = session.sql(raw_query).to_pandas()

        if raw_df.empty:
            print(f"   ℹ️  No CLINIC_RECOMMENDATION_REASON_RAW_DATA found for {department_name} on {target_date}")
            return True

        print(f"   📈 Loaded {len(raw_df)} clinic-reasons rows from Snowflake")

        # Step 2: Parse JSON and aggregate distinct conversations per category
        category_to_chat_ids = {}
        parsed_count = 0
        parse_errors = 0

        for _, row in raw_df.iterrows():
            conversation_id = row['CONVERSATION_ID']
            llm_output = row['LLM_RESPONSE']

            parsed = None
            if isinstance(llm_output, (dict, list)):
                parsed = llm_output
            elif isinstance(llm_output, str) and llm_output.strip():
                parsed = safe_json_parse(llm_output)

            if isinstance(parsed, dict):
                clinic_reasons = parsed.get('ClinicReasons')
            elif isinstance(parsed, list):
                clinic_reasons = parsed
            else:
                clinic_reasons = None

            if isinstance(clinic_reasons, list):
                parsed_count += 1
                seen_categories = set()
                for item in clinic_reasons:
                    if isinstance(item, dict):
                        cat = item.get('Category')
                        if cat is None:
                            continue
                        cat_str = str(cat).strip()
                        # Exclude placeholders
                        if cat_str.upper() in {'NA', 'N/A', 'NULL', 'NONE', ''}:
                            continue
                        seen_categories.add(cat_str)
                for cat_str in seen_categories:
                    category_to_chat_ids.setdefault(cat_str, set()).add(conversation_id)
            else:
                parse_errors += 1

        if not category_to_chat_ids:
            print("   ⚠️  No valid categories found to summarize")
            return True

        # Step 3: Build summary rows
        summary_rows = []
        for category_name, chat_ids in category_to_chat_ids.items():
            summary_rows.append({
                'CATEGORY_NAME': category_name,
                'NUMBER_OF_CHATS': int(len(chat_ids))
            })

        summary_df = pd.DataFrame(summary_rows)
        # Sort for readability
        summary_df = summary_df.sort_values(by=['NUMBER_OF_CHATS', 'CATEGORY_NAME'], ascending=[False, True]).reset_index(drop=True)

        # Step 4: Insert into CLINIC_RECOMMENDATION_REASON_SUMMARY
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='CLINIC_RECOMMENDATION_REASON_SUMMARY',
            department=department_name,
            target_date=target_date,
            dataframe=summary_df,
            columns=list(summary_df.columns)
        )

        if not insert_success or insert_success.get('status') != 'success':
            print("   ❌ Failed to insert clinic reasons summary data")
            return False

        print(f"   ✅ Clinic reasons summary inserted: {len(summary_df)} rows (parsed={parsed_count}, errors={parse_errors})")
        return True

    except Exception as e:
        error_details = format_error_details(e, 'CLINIC REASONS SUMMARY REPORT')
        print(f"   ❌ Failed to create clinic reasons summary report: {str(e)}")
        print(error_details)
        return False

def create_categorizing_summary_report(session: snowpark.Session, parsed_df, department_name: str, target_date):
    """
    Create categorizing summary report and store in Snowflake table
    
    Args:
        session: Snowflake session
        parsed_df: DataFrame with parsed categorizing results
        department_name: Name of the department being analyzed
        target_date: Target date for analysis
    
    Returns:
        Success status and summary statistics
    """
    print(f"📊 Creating categorizing summary report for {department_name} on {target_date}...")
    
    try:
        # Precompute unique chat ids and mappings to apply the requested formulas
        total_chats = parsed_df['chat_id'].nunique() if 'chat_id' in parsed_df.columns else len(parsed_df)

        # Map: category -> set(chat_id) where category appears
        category_to_chat_ids = {}
        for _, row in parsed_df.iterrows():
            chat_id = row['chat_id'] if 'chat_id' in parsed_df.columns else _
            for cat in row['categories']:
                category_to_chat_ids.setdefault(cat, set()).add(chat_id)

        # Map: cause (category_causing_intervention_transfer) -> set(chat_id)
        cause_to_chat_ids = {}
        # Map: (cause, type) where type in {Intervention, Transfer} -> set(chat_id)
        cause_type_to_chat_ids = {}
        for _, row in parsed_df.iterrows():
            chat_id = row['chat_id'] if 'chat_id' in parsed_df.columns else _
            cause = row.get('category_causing_intervention_transfer', 'N/A')
            itype = row.get('intervention_or_transfer', 'N/A')
            cause_to_chat_ids.setdefault(cause, set()).add(chat_id)
            if itype in ['Intervention', 'Transfer']:
                cause_type_to_chat_ids.setdefault((cause, itype), set()).add(chat_id)

        all_categories = sorted(category_to_chat_ids.keys())
        summary_data = []

        for category in all_categories:
            if category in ['Parse_Error', 'N/A', '']:
                continue

            chats_with_category = category_to_chat_ids.get(category, set())
            category_count = len(chats_with_category)
            if category_count == 0:
                continue

            # 1. Count[X]
            count_x = category_count
            # 2. Category %
            category_pct = (count_x / total_chats * 100) if total_chats > 0 else 0.0
            # 3. Coverage Per Category %: 100 - (caused_by_X / Count[X]) * 100
            caused_by_x = len(cause_to_chat_ids.get(category, set()))
            coverage_pct = 100.0 - ((caused_by_x / count_x) * 100.0) if count_x > 0 else 0.0
            # 4. Intervention By Agent %: (cause==X AND Intervention)/TOTAL * 100
            intervention_num = len(cause_type_to_chat_ids.get((category, 'Intervention'), set()))
            intervention_pct = (intervention_num / total_chats * 100) if total_chats > 0 else 0.0
            # 5. Transferred by Bot %: (cause==X AND Transfer)/TOTAL * 100
            transfer_num = len(cause_type_to_chat_ids.get((category, 'Transfer'), set()))
            transfer_pct = (transfer_num / total_chats * 100) if total_chats > 0 else 0.0
            # 6. %AllChatsNotHandled[X]
            all_not_handled_pct = intervention_pct + transfer_pct
            
            summary_data.append({
                'CATEGORY': category,
                'COUNT': count_x,
                'CATEGORY_PCT': f"{round(category_pct, 2):.2f}%",
                'COVERAGE_PER_CATEGORY_PCT': f"{round(coverage_pct, 2):.2f}%",
                'INTERVENTION_BY_AGENT_PCT': f"{round(intervention_pct, 2):.2f}%",
                'TRANSFERRED_BY_BOT_PCT': f"{round(transfer_pct, 2):.2f}%",
                'CHATS_NOT_HANDLED_PCT': f"{round(all_not_handled_pct, 2):.2f}%"
            })
        
        # Add TOTAL row
        # - COUNT: total chats analyzed
        # - CATEGORY_PCT: 100%
        # - COVERAGE_PER_CATEGORY_PCT: 100 - (distinct chats with any cause / total) * 100
        # - INTERVENTION_BY_AGENT_PCT: overall Intervention percentage
        # - TRANSFERRED_BY_BOT_PCT: overall Transfer percentage
        # - CHATS_NOT_HANDLED_PCT: overall (Intervention or Transfer) percentage
        # Chats with a real cause (exclude 'N/A' and similar placeholders)
        caused_by_total_ids = set()
        for cause_key, s in cause_to_chat_ids.items():
            if str(cause_key).strip() not in ['N/A', 'NA', 'NULL', 'None', 'Parse_Error', '']:
                caused_by_total_ids |= s
        intervention_ids = set()
        transfer_ids = set()
        for (cause_key, type_key), s in cause_type_to_chat_ids.items():
            if type_key == 'Intervention':
                intervention_ids |= s
            elif type_key == 'Transfer':
                transfer_ids |= s
        total_intervention_pct = (len(intervention_ids) / total_chats * 100) if total_chats > 0 else 0.0
        total_transfer_pct = (len(transfer_ids) / total_chats * 100) if total_chats > 0 else 0.0
        total_coverage_pct = 100.0 - ((len(caused_by_total_ids) / total_chats * 100.0) if total_chats > 0 else 0.0)
        total_not_handled_pct = ((len(intervention_ids | transfer_ids) / total_chats) * 100.0) if total_chats > 0 else 0.0

        summary_data.append({
            'CATEGORY': 'TOTAL',
            'COUNT': total_chats,
            'CATEGORY_PCT': f"{100.0:.2f}%",
            'COVERAGE_PER_CATEGORY_PCT': f"{round(total_coverage_pct, 2):.2f}%",
            'INTERVENTION_BY_AGENT_PCT': f"{round(total_intervention_pct, 2):.2f}%",
            'TRANSFERRED_BY_BOT_PCT': f"{round(total_transfer_pct, 2):.2f}%",
            'CHATS_NOT_HANDLED_PCT': f"{round(total_not_handled_pct, 2):.2f}%"
            })
        
        # Create summary DataFrame
        summary_df = pd.DataFrame(summary_data)
        
        # Sort by Count (descending)
        if len(summary_df) > 0:
            summary_df = summary_df.sort_values('COUNT', ascending=False)
        
        if summary_df.empty:
            print(f"   ⚠️  No valid categories found for summary")
            return True, {'total_categories': 0}
        
        # Compute overall chats not handled (Intervention or Transfer) as global metric
        if 'chat_id' in parsed_df.columns:
            not_handled_ids = set(parsed_df.loc[parsed_df['intervention_or_transfer'].isin(['Intervention', 'Transfer']), 'chat_id'])
        else:
            not_handled_ids = set(parsed_df.loc[parsed_df['intervention_or_transfer'].isin(['Intervention', 'Transfer'])].index)
        chats_not_handled = len(not_handled_ids)
        pct_all_chats_not_handled = (chats_not_handled / total_chats * 100) if total_chats > 0 else 0.0

        # Import the insert function from processor module
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        
        # Insert summary data into categorizing summary table
        dynamic_columns = list(summary_df.columns)
        
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='CATEGORIZING_SUMMARY',
            department=department_name,  # Use specific department
            target_date=target_date,
            dataframe=summary_df,
            columns=dynamic_columns
        )
        
        if not insert_success or insert_success.get('status') != 'success':
            print(f"   ❌ Failed to insert categorizing summary data")
            return False, {'error': 'Failed to insert summary data'}
        
        # Show quick summary
        print(f"\n   📊 Categorizing Summary Report:")
        print(f"   Total conversations analyzed: {total_chats}")
        print(f"   Total categories found: {len(summary_df)}")
        print(f"   Overall chats not handled by bot: {chats_not_handled} ({pct_all_chats_not_handled:.1f}%)")
        
        # Show top 5 categories by count
        if len(summary_df) > 0:
            print(f"\n   Top categories by volume:")
            for i, row in summary_df.head(5).iterrows():
                print(f"     {i+1}. {row['CATEGORY']}: {row['COUNT']} chats ({row['CATEGORY_PCT']}%)")
                print(f"         Coverage: {row['COVERAGE_PER_CATEGORY_PCT']}%, Intervention: {row['INTERVENTION_BY_AGENT_PCT']}%, Transfer: {row['TRANSFERRED_BY_BOT_PCT']}%")
        
        # Show overall intervention/transfer split
        int_counts = parsed_df['intervention_or_transfer'].value_counts()
        print(f"\n   Overall Intervention/Transfer split:")
        for int_type, count in int_counts.items():
            percentage = (count / total_chats * 100)
            print(f"     {int_type}: {count} ({percentage:.1f}%)")
        
        summary_stats = {
            'total_conversations': total_chats,
            'total_categories': len(summary_df),
            'chats_not_handled': chats_not_handled,
            'pct_all_chats_not_handled': pct_all_chats_not_handled,
            'rows_inserted': len(summary_df)
        }
        
        return True, summary_stats
        
    except Exception as e:
        error_details = format_error_details(e, "CATEGORIZING SUMMARY REPORT")
        print(f"   ❌ Failed to create categorizing summary report: {str(e)}")
        print(error_details)
        return False, {'error': str(e)}
    
def calculate_policy_violation_metrics(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate policy violation metrics from POLICY_VIOLATION_RAW_DATA.

    Metrics computed (percentages rounded to 1 decimal):
      - A_MISSING_POLICY_PERCENTAGE: Missing Policy chats / Total chats analyzed * 100
      - B_MISSING_POLICY_PERCENTAGE: Missing Policy chats / Chats with non-null violation_type * 100
      - A_UNCLEAR_POLICY_PERCENTAGE: Unclear Policy chats / Total chats analyzed * 100
      - B_UNCLEAR_POLICY_PERCENTAGE: Unclear Policy chats / Chats with non-null violation_type * 100
      - A_WRONG_POLICY_PERCENTAGE: Wrong Answer chats / Total chats analyzed * 100
      - B_WRONG_POLICY_PERCENTAGE: Wrong Answer chats / Chats with non-null violation_type * 100

    Also returns a JSON summary string with counts and denominators, and calls

    
    Returns:
      Tuple: (a_missing_pct, b_missing_pct, a_unclear_pct, b_unclear_pct, a_wrong_pct, b_wrong_pct, analysis_summary_json)
    """
    print(f"📊 CALCULATING POLICY VIOLATION METRICS...")

    try:
        # Resolve table from departments config if available
        from snowflake_llm_config import get_snowflake_llm_departments_config
        departments_config = get_snowflake_llm_departments_config()
        llm_prompts = departments_config.get(department_name, {}).get('llm_prompts', {})
        if 'policy_violation' in llm_prompts:
            table_name = llm_prompts['policy_violation'].get('table_name', 'POLICY_VIOLATION_RAW_DATA')
        else:
            table_name = 'POLICY_VIOLATION_RAW_DATA'

        query = f"""
        SELECT 
            CONVERSATION_ID,
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.{table_name}
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROMPT_TYPE = 'policy_violation'
          AND PROCESSING_STATUS = 'COMPLETED'
        """

        results_df = session.sql(query).to_pandas()
        if results_df.empty:
            print(f"   ℹ️  No POLICY_VIOLATION_RAW_DATA data found for {department_name} on {target_date}")
            
            empty_summary = json.dumps({
                    "chats_analyzed": 0,
                    "chats_parsed": 0,
                    "chats_failed": 0,
                    "failure_percentage": 0.0
                }, indent=2)
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, empty_summary

        print(f"   📊 Found {len(results_df)} policy violation records for {department_name} on {target_date}")

        total_chats_analyzed = len(results_df)
        parsed_conversations = 0
        chats_with_non_null_violation = 0
        missing_policy_chats = 0
        unclear_policy_chats = 0
        wrong_answer_chats = 0

        # Helper to normalize labels
        def normalize_label(value):
            try:
                if value is None:
                    return None
                text = str(value).strip()
                if text == "":
                    return None
                lowered = text.lower()
                if lowered in {"null", "n/a", "na", "none"}:
                    return None
                return lowered
            except Exception:
                return None

        # Iterate records and extract violation types at chat level
        for _, row in results_df.iterrows():
            llm_response = row['LLM_RESPONSE']
            parsed = None
            if isinstance(llm_response, (dict, list)):
                parsed = llm_response
            elif isinstance(llm_response, str) and llm_response.strip():
                parsed = safe_json_parse(llm_response)

            found_types = set()

            try:
                if isinstance(parsed, dict):
                    parsed_conversations += 1
                    # Prefer nested array under 'violations'
                    violations = parsed.get('violations')
                    if isinstance(violations, list):
                        for item in violations:
                            if isinstance(item, dict):
                                vt = (item.get('violation_type') or item.get('violationType') or item.get('ViolationType'))
                                norm = normalize_label(vt)
                                if norm:
                                    found_types.add(norm)
                            elif isinstance(item, str):
                                norm = normalize_label(item)
                                if norm:
                                    found_types.add(norm)
                    # Fallback to root-level key if present
                    if not found_types:
                        vt = (parsed.get('violation_type') or parsed.get('violationType') or parsed.get('ViolationType'))
                        norm = normalize_label(vt)
                        if norm:
                            found_types.add(norm)
                elif isinstance(parsed, list):
                    parsed_conversations += 1
                    for item in parsed:
                        if isinstance(item, dict):
                            vt = (item.get('violation_type') or item.get('violationType') or item.get('ViolationType'))
                            norm = normalize_label(vt)
                            if norm:
                                found_types.add(norm)
                        elif isinstance(item, str):
                            norm = normalize_label(item)
                            if norm:
                                found_types.add(norm)
            except Exception:
                pass

            # Update counts
            if found_types:
                chats_with_non_null_violation += 1
                if 'missing policy' in found_types:
                    missing_policy_chats += 1
                if 'unclear policy' in found_types:
                    unclear_policy_chats += 1
                if 'wrong answer' in found_types or 'wrong policy' in found_types:
                    wrong_answer_chats += 1

        # Denominators: only successfully parsed chats are considered
        denom_all = parsed_conversations
        denom_non_null = chats_with_non_null_violation

        # Percentages (A: over all, B: over non-null)
        a_missing = (missing_policy_chats / denom_all * 100) if denom_all > 0 else 0.0
        b_missing = (missing_policy_chats / denom_non_null * 100) if denom_non_null > 0 else 0.0
        a_unclear = (unclear_policy_chats / denom_all * 100) if denom_all > 0 else 0.0
        b_unclear = (unclear_policy_chats / denom_non_null * 100) if denom_non_null > 0 else 0.0
        a_wrong = (wrong_answer_chats / denom_all * 100) if denom_all > 0 else 0.0
        b_wrong = (wrong_answer_chats / denom_non_null * 100) if denom_non_null > 0 else 0.0

        # Build standardized parsing summary
        failure_stats = json.dumps({
            "chats_analyzed": total_chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": total_chats_analyzed - parsed_conversations,
            "failure_percentage": round(((total_chats_analyzed - parsed_conversations) / total_chats_analyzed) * 100, 1) if total_chats_analyzed > 0 else 0.0
        }, indent=2)

        print(f"   📈 Policy Violation Analysis Results:")
        print(f"   Total conversations analyzed: {total_chats_analyzed}")
        print(f"   Successfully parsed: {parsed_conversations}")
        print(f"   Failed to parse: {total_chats_analyzed - parsed_conversations}")
        print(f"   With non-null violation_type: {chats_with_non_null_violation}")
        print(f"   Missing Policy chats: {missing_policy_chats}")
        print(f"   Unclear Policy chats: {unclear_policy_chats}")
        print(f"   Wrong Answer chats: {wrong_answer_chats}")
        print(f"   A% Missing/Unclear/Wrong = {round(a_missing,1)}/{round(a_unclear,1)}/{round(a_wrong,1)}")
        print(f"   B% Missing/Unclear/Wrong = {round(b_missing,1)}/{round(b_unclear,1)}/{round(b_wrong,1)}")

        return (
            round(a_missing, 1),
            round(b_missing, 1),
            round(a_unclear, 1),
            round(b_unclear, 1),
            round(a_wrong, 1),
            round(b_wrong, 1),
            failure_stats
        )

    except Exception as e:
        error_details = format_error_details(e, "POLICY VIOLATION METRICS CALCULATION")
        print(f"   ❌ Failed to calculate policy violation metrics: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, empty_stats


def calculate_missing_policy_metrics(session: snowpark.Session, department_name: str, target_date="2025-07-27"):
    """
    Calculate Missing Policy metrics from MISSING_POLICY_RAW_DATA.

    LLM_RESPONSE sample structure:
    {
      "missingPolicy": "Yes|No|True|False",
      "Category": "...",
      "Justification": "...",
      "botHallucination": "...",
      "hallucinationJustification": "..."
    }

    Returns (in order):
      - float: missing policy percentage = (count(missingPolicy == Yes) / parsed) * 100
      - int: missing policy count
      - str: analysis summary JSON {chats_analyzed, chats_parsed, chats_failed, failure_percentage}
    """
    print(f"📊 CALCULATING MISSING POLICY METRICS...")
    try:
        query = f"""
        SELECT 
            DEPARTMENT,
            LLM_RESPONSE,
            PROCESSING_STATUS
        FROM LLM_EVAL.PUBLIC.MISSING_POLICY_RAW_DATA 
        WHERE DATE(DATE) = DATE('{target_date}')
          AND DEPARTMENT = '{department_name}'
          AND PROMPT_TYPE = 'missing_policy'
          AND PROCESSING_STATUS = 'COMPLETED'
          AND LLM_RESPONSE IS NOT NULL
          AND LLM_RESPONSE != ''
        """
        results_df = session.sql(query).to_pandas()

        if results_df.empty:
            print(f"   ℹ️  No MISSING_POLICY_RAW_DATA data found for {department_name} on {target_date}")
            empty_stats = json.dumps({
                "chats_analyzed": 0,
                "chats_parsed": 0,
                "chats_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return 0.0, 0, empty_stats

        print(f"   📊 Found {len(results_df)} missing policy records for {department_name} on {target_date}")

        chats_analyzed = len(results_df)
        parsed_conversations = 0
        missing_policy_count = 0

        for _, row in results_df.iterrows():
            try:
                llm_response = row['LLM_RESPONSE']
                parsed = None
                if isinstance(llm_response, dict):
                    parsed = llm_response
                elif isinstance(llm_response, str) and llm_response.strip():
                    parsed = safe_json_parse(llm_response)

                if isinstance(parsed, dict):
                    parsed_conversations += 1
                    mp_value = parsed.get('missingPolicy')
                    is_missing = parse_boolean_flexible(mp_value) is True
                    if is_missing:
                        missing_policy_count += 1
            except Exception:
                # skip malformed rows
                continue

        if parsed_conversations == 0:
            print("   ⚠️  No valid conversations found for missing policy analysis")
            empty_stats = json.dumps({
                "chats_analyzed": chats_analyzed,
                "chats_parsed": 0,
                "chats_failed": chats_analyzed,
                "failure_percentage": 100.0 if chats_analyzed > 0 else 0.0
            }, indent=2)
            return 0.0, 0, empty_stats

        percentage = (missing_policy_count / parsed_conversations) * 100.0

        print(f"   📈 Missing Policy Results: {missing_policy_count}/{parsed_conversations} → {percentage:.1f}%")

        failure_stats = json.dumps({
            "chats_analyzed": chats_analyzed,
            "chats_parsed": parsed_conversations,
            "chats_failed": chats_analyzed - parsed_conversations,
            "failure_percentage": round(((chats_analyzed - parsed_conversations) / chats_analyzed) * 100, 1) if chats_analyzed > 0 else 0.0
        }, indent=2)

        return round(percentage, 1), int(missing_policy_count), failure_stats

    except Exception as e:
        error_details = format_error_details(e, "MISSING POLICY METRICS CALCULATION")
        print(f"   ❌ Failed to calculate missing policy metrics: {str(e)}")
        print(error_details)
        empty_stats = json.dumps({
            "chats_analyzed": 0,
            "chats_parsed": 0,
            "chats_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return 0.0, 0, empty_stats

def create_shadowing_automation_summary_report(session: snowpark.Session, department_name: str, target_date):
    """
    Create SHADOWING_AUTOMATION_SUMMARY by processing reported issues sequentially for target_date.

    Returns: (processed_count, unique_issues_count, analysis_summary_json, success_flag)
    """
    print(f"📊 Creating SHADOWING_AUTOMATION_SUMMARY for {department_name} on {target_date}...")
    try:
        from snowflake_llm_config import get_snowflake_llm_departments_config
        departments_config = get_snowflake_llm_departments_config()
        agent_names = get_department_agent_names_snowflake(session, department_name, departments_config)
        if not agent_names:
            print(f"   ⚠️  No agents found for {department_name}; skipping")
            stats = json.dumps({
                "issues_analyzed": 0,
                "issues_parsed": 0,
                "issues_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return stats, True

        agent_list = ", ".join(["'" + a.replace("'", "''").upper() + "'" for a in sorted(agent_names)])
        query = f"""
        SELECT 
            ISSUE_ID,
            ISSUE_STATUS,
            ISSUE_TYPE,
            CREATION_DATE,
            "What happened and what should have been done ?" AS ISSUE_DESCRIPTION,
        FROM LLM_EVAL.RAW_DATA.CHATCC_REPORTED_ISSUES
        WHERE DATE(CREATION_DATE) = DATE('{target_date}')
          AND UPPER(TRIM(REPORTER)) IN ({agent_list})
        ORDER BY CREATION_DATE ASC, ISSUE_ID ASC
        """
        df = session.sql(query).to_pandas()

        if df.empty:
            print(f"   ℹ️  No reported issues for {department_name} on {target_date}")
            stats = json.dumps({
                "issues_analyzed": 0,
                "issues_parsed": 0,
                "issues_failed": 0,
                "failure_percentage": 0.0
            }, indent=2)
            return stats, True

        print(f"   📊 Found {len(df)} reported issues for {department_name} on {target_date} and agents {agent_list}")
        
        unique_titles_set = set()
        title_to_issue_ids = {}
        title_to_first_type = {}
        title_to_any_done = {}
        parsed = 0
        failed = 0

        from prompts import UNIQUE_ISSUES_PROMPT

        def call_llm(system_prompt_text: str, prompt_text: str) -> str:
            safe_system = system_prompt_text.replace("'", "''")
            safe_prompt = prompt_text.replace("'", "''")
            sql = f"""
            SELECT gemini_chat_system(
                '{safe_prompt}',
                '{safe_system}',
                'gemini-2.5-pro',
                0.2,
                7000
            ) AS llm_response
            """
            res = session.sql(sql).collect()
            return res[0]['LLM_RESPONSE'] if res else None

        for _, row in df.iterrows():
            issue_id = row['ISSUE_ID']
            status = str(row.get('ISSUE_STATUS', '') or '')
            issue_type = str(row.get('ISSUE_TYPE', '') or '')
            desc = str(row.get('ISSUE_DESCRIPTION', '') or '')

            known_unique = "\n".join(sorted(unique_titles_set)) if unique_titles_set else ""
            system_prompt_text = UNIQUE_ISSUES_PROMPT.replace("{uniqueIssues}", known_unique)

            verdict_raw = None
            try:
                verdict_raw = call_llm(system_prompt_text, desc)
            except Exception as e:
                print(f"   ⚠️  LLM call failed for issue {issue_id}: {str(e)}")

            selected_title = None
            if isinstance(verdict_raw, str):
                s = verdict_raw.strip()
                if s.startswith('<UniqueIssue>') and '</UniqueIssue>' in s:
                    import re as _re
                    m = _re.search(r"<Title>([\s\S]*?)</Title>", s)
                    if m:
                        selected_title = m.group(1).strip()
                elif s.upper().startswith('ALREADY REPORTED AS'):
                    start = s.find('"')
                    end = s.rfind('"')
                    if start != -1 and end != -1 and end > start:
                        selected_title = s[start+1:end].strip()

            if selected_title:
                unique_titles_set.add(selected_title)
                title_to_issue_ids.setdefault(selected_title, set()).add(str(int(issue_id)) if pd.notna(issue_id) else str(issue_id))
                if issue_type:
                    if selected_title not in title_to_first_type:
                        title_to_first_type[selected_title] = issue_type
                # Track if any status is Done → Fixed
                try:
                    if str(status).strip().lower() == 'done':
                        title_to_any_done[selected_title] = True
                    else:
                        title_to_any_done.setdefault(selected_title, False)
                except Exception:
                    title_to_any_done.setdefault(selected_title, False)
                parsed += 1
            else:
                failed += 1

        if not title_to_issue_ids:
            print("   ⚠️  No rows processed for SHADOWING_AUTOMATION_SUMMARY")
            stats = json.dumps({
                "issues_analyzed": len(df),
                "issues_parsed": 0,
                "issues_failed": len(df),
                "failure_percentage": 100.0 if len(df) > 0 else 0.0
            }, indent=2)
            return stats, True

        # Aggregate into required summary columns
        summary_rows = []
        from collections import Counter as _Counter
        for title, ids_set in title_to_issue_ids.items():
            ids_list = sorted([i for i in ids_set if i is not None])
            frequency = len(ids_list)
            # Category: first encountered ISSUE_TYPE for this title
            category = str(title_to_first_type.get(title, 'N/A'))
            if frequency >= 4:
                severity = 'Severe'
            elif frequency >= 2:
                severity = 'Moderate'
            else:
                severity = 'Low'
            status_val = 'Fixed' if title_to_any_done.get(title, False) else 'Not Fixed'
            unique_block = f"<UniqueIssue>\n      <Title>{title}</Title>\n</UniqueIssue>"
            summary_rows.append({
                'UNIQUE_ISSUES': unique_block,
                'CATEGORY': category,
                'SEVERITY': severity,
                'FREQUENCY': int(frequency),
                'STATUS': status_val,
                'ISSUE_IDS': ", ".join(ids_list)
            })

        summary_df = pd.DataFrame(summary_rows)
        from snowflake_llm_processor import insert_raw_data_with_cleanup
        insert_success = insert_raw_data_with_cleanup(
            session=session,
            table_name='SHADOWING_AUTOMATION_SUMMARY',
            department=department_name,
            target_date=target_date,
            dataframe=summary_df,
            columns=list(summary_df.columns)
        )

        stats = json.dumps({
            "issues_analyzed": int(len(df)),
            "issues_parsed": int(parsed),
            "issues_failed": int(failed),
            "failure_percentage": round((failed / len(df)) * 100, 1) if len(df) > 0 else 0.0,
            "unique_issues": int(len(unique_titles_set))
        }, indent=2)

        if not insert_success or insert_success.get('status') != 'success':
            print("   ❌ Failed to insert SHADOWING_AUTOMATION_SUMMARY data")
            return stats, False

        print(f"   ✅ SHADOWING_AUTOMATION_SUMMARY inserted: {len(summary_df)} rows; unique={len(unique_titles_set)}")
        return stats, True

    except Exception as e:
        error_details = format_error_details(e, 'SHADOWING AUTOMATION SUMMARY')
        print(f"   ❌ Failed to create SHADOWING_AUTOMATION_SUMMARY: {str(e)}")
        print(error_details)
        stats = json.dumps({
            "issues_analyzed": 0,
            "issues_parsed": 0,
            "issues_failed": 0,
            "failure_percentage": 0.0
        }, indent=2)
        return stats, False
