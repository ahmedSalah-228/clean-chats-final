"""
XML Conversion Module for Snowflake LLM Analysis
Converts conversation DataFrames to XML format for LLM processing
Adapted from LLM_UTILITIES.py to work with DataFrames directly
"""

import pandas as pd
import json
import xml.sax.saxutils as saxutils
from snowflake_llm_config import get_snowflake_llm_departments_config
from snowflake_llm_helpers import get_execution_id_map, get_tool_name_and_response


def format_tool_with_name_as_xml(tool_name, tool_output, tool_time):
    """
    Convert tool name and output to XML format, showing tool name and all parameters
    """
    escaped_tool_name = saxutils.escape(str(tool_name))
    escaped_tool_time = saxutils.escape(str(tool_time))
    return f"<tool>\n  <n>{escaped_tool_name}</n> \n  <t>{escaped_tool_time}</t>\n</tool>"
    
    if isinstance(tool_output, dict):
        if not tool_output:  # Empty dict
            return f"<tool>\n  <n>{escaped_tool_name}</n>\n  <t>{escaped_tool_time}</t>\n  <o>{{}}</o>\n</tool>"
        
        # Format all parameters/properties
        params_xml = ""
        for key, value in tool_output.items():
            escaped_key = saxutils.escape(str(key))
            if isinstance(value, (dict, list)):
                # Convert complex objects to JSON string
                escaped_value = saxutils.escape(json.dumps(value, indent=2))
            else:
                escaped_value = saxutils.escape(str(value))
            params_xml += f"  <{escaped_key}>{escaped_value}</{escaped_key}>\n"
        
        return f"<tool>\n  <n>{escaped_tool_name}</n>\n  <t>{escaped_tool_time}</t>\n{params_xml}</tool>"
    
    elif isinstance(tool_output, str):
        if not tool_output.strip():  # Empty string
            escaped_output = "{}"
        else:
            escaped_output = saxutils.escape(tool_output)
        return f"<tool>\n  <n>{escaped_tool_name}</n>\n  <t>{escaped_tool_time}</t>\n  <o>{escaped_output}</o>\n</tool>"
    
    else:
        # Handle other types (None, numbers, etc.)
        if tool_output is None or tool_output == "":
            escaped_output = "{}"
        else:
            escaped_output = saxutils.escape(str(tool_output))
        return f"<tool>\n  <n>{escaped_tool_name}</n>\n  <t>{escaped_tool_time}</t>\n  <o>{escaped_output}</o>\n</tool>"


def preprocess_conversation_dataframe(conv_df):
    """
    Preprocess a single conversation DataFrame
    Sort by message timestamp - works directly with Snowflake column names
    """
    # Sort by MESSAGE_SENT_TIME (Snowflake column name)
    if 'MESSAGE_SENT_TIME' in conv_df.columns:
        conv_df = conv_df.sort_values('MESSAGE_SENT_TIME')
    
    return conv_df


def convert_single_conversation_to_xml(conv_df, department_name, include_tool_messages=True, debug_info=None):
    """
    Convert a single conversation DataFrame to XML format
    Adapted from LLM_UTILITIES.py convert_conversation_to_xml()
    
    Args:
        conv_df: DataFrame containing messages for one conversation
        department_name: Department name for skill filtering
    
    Returns:
        XML string representation of the conversation
    """
    # Get department configuration
    departments_config = get_snowflake_llm_departments_config()
    if department_name not in departments_config:
        if isinstance(debug_info, dict):
            debug_info['reason'] = 'department_not_configured'
        return None
        
    dept_config = departments_config[department_name]
    target_bot_skills = dept_config['bot_skills']
    target_agent_skills = dept_config['agent_skills']
    
    # Preprocess the conversation
    conv_df = preprocess_conversation_dataframe(conv_df.copy())
    
    # Check required columns exist (using Snowflake column names)
    required_columns = ['CONVERSATION_ID', 'MESSAGE_SENT_TIME', 'SENT_BY', 'TEXT']
    missing_columns = [col for col in required_columns if col not in conv_df.columns]
    if missing_columns:
        if isinstance(debug_info, dict):
            debug_info['reason'] = 'missing_columns'
            debug_info['details'] = {'missing_columns': missing_columns}
        return None
    
    # Check if conversation contains target skills
    if 'TARGET_SKILL_PER_MESSAGE' in conv_df.columns:
        skills_series = conv_df['TARGET_SKILL_PER_MESSAGE'].fillna('')
        skills = list(set(skills_series.tolist()))
        if not any(skill in target_bot_skills for skill in skills):
            if isinstance(debug_info, dict):
                debug_info['reason'] = 'no_target_skill_match'
                debug_info['details'] = {'skills_found': skills, 'required_bot_skills': target_bot_skills}
            return None
    
    # Get unique participants
    sent_by_series = conv_df['SENT_BY'].fillna('')
    participants = sorted(list(set(sent_by_series.tolist())))
    
    # Check if any participant is 'bot' or 'agent' (case-insensitive)
    has_bot_or_agent = any(p.lower() in ["bot", "agent"] for p in participants)
    has_consumer = any(p.lower() == "consumer" for p in participants)
    if not has_bot_or_agent or not has_consumer:
        if isinstance(debug_info, dict):
            debug_info['reason'] = 'participants_missing'
            debug_info['details'] = {'participants': participants}
        return None
    
    # Get conversation ID
    conv_id = conv_df['CONVERSATION_ID'].iloc[0] if len(conv_df) > 0 else "unknown"
    
    # Start building XML content
    content_parts = []
    
    # Track last message details for duplicate detection
    last_message_time = None
    last_message_text = None
    last_message_sender = None
    last_message_type = None
    
    # Track the last skill seen in the conversation
    last_skill = ""
    is_our_bot = True
    
    # Process each message
    for _, row in conv_df.iterrows():
        # Get message time (using Snowflake column name)
        message_time = row['MESSAGE_SENT_TIME']
        if pd.notna(message_time):
            current_time = str(message_time)
        else:
            current_time = ""
        
        # Get message text
        text_value = row['TEXT']
        current_text = str(text_value) if pd.notna(text_value) else ""
        
        # Get sender (using Snowflake column name)
        sent_by_value = row['SENT_BY']
        current_sender = str(sent_by_value) if pd.notna(sent_by_value) else ""
        
        # Get skill (using Snowflake column name)
        skill_value = row.get('TARGET_SKILL_PER_MESSAGE', '')
        current_skill = str(skill_value) if pd.notna(skill_value) else ""
        
        
        # Get message type (using Snowflake column name)
        message_type_value = row.get('MESSAGE_TYPE', '')
        current_type = str(message_type_value).lower() if pd.notna(message_type_value) else ""

        # Skip transfer and private messages
        if current_type == "transfer" or current_type == "private message" or current_type == "tool response":
            continue
        
        # Handle bot messages from non-target skills
        if current_sender.lower() == "bot" and current_skill not in target_bot_skills:
            current_sender = "Agent_1"

        # Handle empty messages
        if (current_text == "" or pd.isna(text_value)) and current_type == "normal message":
            current_text = "[Doc/Image]"

        # Check if this is a duplicate message (same time, text, sender, and type)
        is_duplicate = (current_time == last_message_time and 
                      current_text == last_message_text and 
                      current_sender == last_message_sender and 
                      current_type == last_message_type)
        
        # Update last skill if we have a skill value and this is not a duplicate
        if current_skill and not is_duplicate and current_skill != "nan":
            last_skill = current_skill
        
        # Add tool message by resolving tool name and matching tool response content
        if current_type == "tool" and current_text and is_our_bot:
            if include_tool_messages:
                tool_time = row.get('MESSAGE_SENT_TIME', '')
                
                tool_name, tool_output = get_tool_name_and_response(conv_df, text_value)
                
                tool_xml = format_tool_with_name_as_xml(tool_name or "Unknown_Tool", tool_output or "{}", tool_time)
                content_parts.append(tool_xml)
            continue

        # If there's a message and it's not a duplicate, add it
        if current_text and not is_duplicate:
            # Escape XML special characters in the message content
            escaped_text = saxutils.escape(current_text)
            
            # Special formatting for system messages
            if current_sender.lower() == "system":
                message_line = f"[SYSTEM: {escaped_text}]"
            else:
                message_line = f"{current_sender}: {escaped_text}"
            
            content_parts.append(message_line)
            
            # Update last message details
            last_message_time = current_time
            last_message_text = current_text
            last_message_sender = current_sender
            last_message_type = current_type
    
    # Only proceed if we have content
    if not content_parts:
        if isinstance(debug_info, dict):
            debug_info['reason'] = 'no_content_after_cleaning'
        return None
    
    # Join all content parts with newlines
    content_xml = "\n\n".join(content_parts)
    
    # Build the full XML structure
    full_xml = f"""<conversation>
<chatID>{saxutils.escape(str(conv_id))}</chatID>
<content>

{content_xml}

</content>
</conversation>"""
    
    return full_xml


def convert_conversations_to_xml_dataframe(filtered_df, department_name, include_tool_messages=True):
    """
    Convert filtered DataFrame conversations to XML format without saving CSV files.
    
    Args:
        filtered_df: Filtered DataFrame from Phase 1 processing
        department_name: Department name for configuration
    
    Returns:
        DataFrame with columns: conversation_id, content_xml_view, department, last_skill
    """
    print(f"    🔄 Converting conversations to XML format for {department_name}...")
    
    if filtered_df.empty:
        print(f"    ⚠️  No conversations to convert")
        return pd.DataFrame(columns=['conversation_id', 'content_xml_view', 'department', 'last_skill'])
    
    xml_conversations = []
    processed_count = 0

    # Debug counters
    total_conversations = 0
    dropped_missing_columns = 0
    dropped_no_target_skill = 0
    dropped_participants_missing = 0
    dropped_no_content = 0
    dropped_other = 0
    
    # Group by conversation ID and process each conversation (using Snowflake column name)
    if 'CONVERSATION_ID' not in filtered_df.columns:
        print(f"    ❌ CONVERSATION_ID column not found in DataFrame")
        return pd.DataFrame(columns=['conversation_id', 'content_xml_view', 'department', 'last_skill'])
    
    execution_id_map = get_execution_id_map(filtered_df, department_name)

    for conv_id, conv_df in filtered_df.groupby('CONVERSATION_ID'):
        total_conversations += 1
        # Convert conversation to XML with debug capture
        drop_info = {}
        xml_content = convert_single_conversation_to_xml(conv_df, department_name, include_tool_messages, debug_info=drop_info)
        
        if xml_content:
            xml_conversations.append({
                'conversation_id': str(conv_id),
                'content_xml_view': xml_content,
                'department': department_name,
                'last_skill': conv_df['SKILL'].iloc[0],
                'execution_id': execution_id_map.get(conv_id, ''),
                'agent_names': ", ".join(sorted(set(conv_df['AGENT_NAME'].dropna().astype(str)))) if 'AGENT_NAME' in conv_df.columns else "",
                'shadowed_by': conv_df['SHADOWED_BY'].iloc[0],
                'customer_name': (conv_df['CUSTOMER_NAME'].dropna().astype(str).iloc[0] if ('CUSTOMER_NAME' in conv_df.columns and not conv_df['CUSTOMER_NAME'].dropna().empty) else ""),
            })
            processed_count += 1
        else:
            # Count and log dropped conversations with reasons
            reason = drop_info.get('reason', 'unknown')
            details = drop_info.get('details', {})
            if reason == 'missing_columns':
                dropped_missing_columns += 1
            elif reason == 'no_target_skill_match':
                dropped_no_target_skill += 1
            elif reason == 'participants_missing':
                dropped_participants_missing += 1
            elif reason == 'no_content_after_cleaning':
                dropped_no_content += 1
            else:
                dropped_other += 1
            # print(f"    🛈 Dropped conversation {conv_id} during XML conversion | reason={reason} | details={details}")
    
    print(f"    ✅ Converted {processed_count} conversations to XML")

    # Print debug summary
    print(f"    ─ Debug: XML conversion funnel ─")
    print(f"      • Total conversations before XML: {total_conversations}")
    print(f"      • Dropped (missing columns): {dropped_missing_columns}")
    print(f"      • Dropped (no per-message bot skill match): {dropped_no_target_skill}")
    print(f"      • Dropped (participants missing): {dropped_participants_missing}")
    print(f"      • Dropped (no content after cleaning): {dropped_no_content}")
    print(f"      • Dropped (other): {dropped_other}")
    print(f"      • Final converted: {processed_count}")
    
    return pd.DataFrame(xml_conversations)


def validate_xml_conversion(xml_conversations_df, department_name):
    """
    Validate the XML conversion results
    
    Args:
        xml_conversations_df: DataFrame with XML conversations
        department_name: Department name
    
    Returns:
        Validation results dictionary
    """
    validation_results = {
        'total_conversations': len(xml_conversations_df),
        'valid_xml_count': 0,
        'empty_xml_count': 0,
        'errors': []
    }
    
    if xml_conversations_df.empty:
        validation_results['errors'].append("No conversations in XML DataFrame")
        return validation_results
    
    # Check each XML conversation
    for _, row in xml_conversations_df.iterrows():
        xml_content = row.get('content_xml_view', '')
        
        if not xml_content or xml_content.strip() == '':
            validation_results['empty_xml_count'] += 1
        else:
            # Basic XML structure validation
            if '<conversation>' in xml_content and '</conversation>' in xml_content:
                if '<chatID>' in xml_content and '<content>' in xml_content:
                    validation_results['valid_xml_count'] += 1
                else:
                    validation_results['errors'].append(f"Missing XML elements in conversation {row.get('conversation_id', 'unknown')}")
            else:
                validation_results['errors'].append(f"Invalid XML structure in conversation {row.get('conversation_id', 'unknown')}")
    
    validation_results['success_rate'] = (
        validation_results['valid_xml_count'] / validation_results['total_conversations'] * 100
    ) if validation_results['total_conversations'] > 0 else 0
    
    return validation_results


def get_xml_sample(xml_conversations_df, sample_size=1):
    """
    Get a sample of XML conversations for inspection
    
    Args:
        xml_conversations_df: DataFrame with XML conversations
        sample_size: Number of samples to return
    
    Returns:
        Sample XML conversations
    """
    if xml_conversations_df.empty:
        return []
    
    sample_df = xml_conversations_df.head(sample_size)
    samples = []
    
    for _, row in sample_df.iterrows():
        samples.append({
            'conversation_id': row.get('conversation_id', 'unknown'),
            'department': row.get('department', 'unknown'),
            'last_skill': row.get('last_skill', 'unknown'),
            'xml_preview': row.get('content_xml_view', '')[:500] + '...' if len(row.get('content_xml_view', '')) > 500 else row.get('content_xml_view', '')
        })
    
    return samples