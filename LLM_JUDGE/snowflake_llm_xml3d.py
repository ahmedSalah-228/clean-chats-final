"""
XML3D Processor for Snowflake conversation data
Converts Snowflake conversation DataFrames to XML format grouped by customer name
Output: One row per customer with all their chats in XML format
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
    return f"<tool>\n  <n>{escaped_tool_name}</n> \n <t>{escaped_tool_time}</t>\n</tool>"
    
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


def convert_conversations_to_xml3d(filtered_df, department_name):
    """
    Convert Snowflake conversation DataFrame to XML3D format grouped by customer name
    
    Args:
        filtered_df: Filtered DataFrame from Phase 1 processing (Snowflake column names)
        department_name: Department name for configuration
    
    Returns:
        List of dictionaries with customer_name, content_xml_view, chat_count, customer_names, agent_names
    """
    print(f"🔄 Converting conversations to XML3D format for {department_name}...")
    
    if filtered_df.empty:
        print(f"    ⚠️  No conversations to convert to XML3D")
        return []
    
    # Get department configuration
    departments_config = get_snowflake_llm_departments_config()
    if department_name not in departments_config:
        print(f"    ❌ Department {department_name} not found in configuration")
        return []
        
    dept_config = departments_config[department_name]
    target_skills = dept_config['bot_skills']
    
    # Check required columns exist (using Snowflake column names)
    required_columns = ['CONVERSATION_ID', 'MESSAGE_SENT_TIME', 'SENT_BY', 'TEXT']
    missing_columns = [col for col in required_columns if col not in filtered_df.columns]
    if missing_columns:
        print(f"    ❌ Missing required columns for XML3D conversion: {missing_columns}")
        return []
    
    # Step 1: First group by Conversation ID to get complete conversations
    conversation_ids = filtered_df['CONVERSATION_ID'].unique()
    print(f"    📋 Found {len(conversation_ids)} unique conversations")
    
    # Step 2: Process each conversation and extract customer name
    complete_conversations = {}  # {customer_name: [conversation_data, ...]}

    execution_id_map = get_execution_id_map(filtered_df, department_name)
    
    processed_conversations = 0
    for conv_id in conversation_ids:
        # Get all messages for this conversation
        conv_messages = filtered_df[filtered_df['CONVERSATION_ID'] == conv_id]
        
        # Check if conversation contains target skills
        if 'TARGET_SKILL_PER_MESSAGE' in conv_messages.columns:
            skills_series = conv_messages['TARGET_SKILL_PER_MESSAGE'].fillna('')
            skills = list(set(skills_series.tolist()))
            if not any(skill in target_skills for skill in skills):
                continue
        
        # Get unique participants
        sent_by_series = conv_messages['SENT_BY'].fillna('')
        participants = sorted(list(set(sent_by_series.tolist())))
        
        # Check if any participant is 'bot' or 'agent' (case-insensitive)
        has_bot_or_agent = any(p.lower() in ["bot", "agent"] for p in participants)
        has_consumer = any(p.lower() == "consumer" for p in participants)
        if not has_bot_or_agent or not has_consumer:
            continue
        
        # Extract customer name from any message in this conversation that has it
        customer_names_in_conv = conv_messages.get('CUSTOMER_NAME', pd.Series()).fillna('').astype(str)
        valid_customer_names = [name for name in customer_names_in_conv if name and name.strip() and name != 'nan' and name.lower() != 'unknown']
        
        if valid_customer_names:
            # Use the first valid customer name found
            customer_name = valid_customer_names[0].strip()
        else:
            # Skip conversations without valid customer names or with "Unknown" names
            continue
        
        # Get first message timestamp for this conversation
        first_message_time = conv_messages['MESSAGE_SENT_TIME'].min()
        first_message_time_str = str(first_message_time) if pd.notna(first_message_time) else ""
        
        # Get agent names (non-consumer, non-bot participants)
        agent_names = [p for p in participants if p.lower() not in ['consumer', 'bot', 'system']]
        agent_names_str = ', '.join(agent_names) if agent_names else ''

        # Get last skill from conversation (using Snowflake column name)
        last_skill = ""
        if 'TARGET_SKILL_PER_MESSAGE' in conv_messages.columns:
            skills = conv_messages['TARGET_SKILL_PER_MESSAGE'].dropna()
            if not skills.empty:
                last_skill = str(skills.iloc[-1])
        
        # Process the conversation content
        conversation_xml = process_single_conversation_snowflake(conv_messages, conv_id, first_message_time_str, target_skills, department_name)
        
        if conversation_xml:
            # Add to customer's conversation list
            if customer_name not in complete_conversations:
                complete_conversations[customer_name] = []
            complete_conversations[customer_name].append({
                'xml': conversation_xml,
                'first_time': pd.to_datetime(first_message_time_str) if first_message_time_str else pd.Timestamp.min,
                'agent_names': agent_names_str,
                'conversation_id': conv_id,
                'last_skill': last_skill,
            })
            processed_conversations += 1
    
    print(f"    ✅ Processed {processed_conversations} valid conversations for {len(complete_conversations)} customers")
    
    # Step 3: Group conversations by customer name and create final XML
    xml3d_conversations = []
    
    for customer_name, conversations in complete_conversations.items():
        # Sort conversations by first message time
        conversations.sort(key=lambda x: x['first_time'])
        
        # Combine all conversations for this customer
        customer_chats_xml = [conv['xml'] for conv in conversations]
        all_chats_xml = "\n\n".join(customer_chats_xml)

        # Collect Last Skill comma separated string for each conversation as they are
        last_skill_combined = ', '.join(str(conv['last_skill']) for conv in conversations)

        # Collect Conversation ID for each conversation as they are
        conversation_id_combined = ', '.join(str(conv['conversation_id']) for conv in conversations)
        
        # Collect all agent names for this customer
        all_agent_names = set()
        for conv in conversations:
            if conv['agent_names']:
                all_agent_names.update(conv['agent_names'].split(', '))
        agent_names_combined = ', '.join(sorted(all_agent_names))
        
        # Build the full conversations XML structure
        conversations_xml = f"""<conversations>
<chat_count>{len(conversations)}</chat_count>

{all_chats_xml}

</conversations>"""
        
        # Add to final list
        xml3d_conversations.append({
            'conversation_id': conversation_id_combined,
            'last_skill': last_skill_combined,
            'customer_name': customer_name,
            'content_xml_view': conversations_xml,
            'chat_count': len(conversations),
            'customer_names': customer_name,  # For compatibility with existing schema
            'agent_names': agent_names_combined,
            'execution_id': execution_id_map.get(conv_id, ''),
        })
    
    print(f"    📊 Generated XML3D for {len(xml3d_conversations)} customers")
    
    # Convert to DataFrame for consistency with other conversion functions
    return pd.DataFrame(xml3d_conversations)


def process_single_conversation_snowflake(conv_messages, conv_id, first_message_time_str, target_skills, department_name):
    """
    Process a single conversation and return its XML representation
    Updated to use Snowflake column names
    """
    # Start building XML content for this conversation
    content_parts = []
    
    # Sort messages by timestamp to ensure chronological order (using Snowflake column name)
    conv_messages_sorted = conv_messages.sort_values('MESSAGE_SENT_TIME')
    
    # Track last message details for duplicate detection
    last_message_time = None
    last_message_text = None
    last_message_sender = None
    last_message_type = None
    
    # Process each message in this conversation (now in chronological order)
    for _, row in conv_messages_sorted.iterrows():
        # Get message time (using Snowflake column name)
        message_time = row['MESSAGE_SENT_TIME']
        if pd.notna(message_time):
            current_time = str(message_time)
        else:
            current_time = ""
        
        # Get message text (using Snowflake column name)
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
        if current_type == "transfer" or current_type == "private message":
            continue
        
        # Handle bot messages from non-target skills
        if current_sender.lower() == "bot" and current_skill not in target_skills:
            current_sender = "Agent_1"
        
        # Handle empty messages
        if (current_text == "" or pd.isna(text_value)) and current_type == "normal message":
            current_text = "[Doc/Image]"
        
        # Check if this is a duplicate message
        is_duplicate = (current_time == last_message_time and 
                      current_text == last_message_text and 
                      current_sender == last_message_sender and 
                      current_type == last_message_type)
        
        # Add tool message by resolving tool name and matching tool response content
        if current_type == "tool" and current_text:
            tool_time = row.get('MESSAGE_SENT_TIME', '')
            
            tool_name, tool_output = get_tool_name_and_response(conv_messages, text_value)
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
    
    # Only return XML if we have content
    if content_parts:
        # Join all content parts with newlines
        content_xml = "\n\n".join(content_parts)
        
        # Build the chat XML structure
        chat_xml = f"""<chat><id>{saxutils.escape(str(conv_id))}</id><first_message_time>{saxutils.escape(first_message_time_str)}</first_message_time><content>

{content_xml}

</content></chat>"""
        
        return chat_xml
    
    return None


def validate_xml3d_conversion(xml3d_conversations_df, department_name):
    """
    Validate the XML3D conversion results
    
    Args:
        xml3d_conversations_df: DataFrame with XML3D conversation data
        department_name: Department name
    
    Returns:
        Validation results dictionary
    """
    validation_results = {
        'total_customers': len(xml3d_conversations_df),
        'valid_xml3d_count': 0,  # Changed to match the processor expectation
        'empty_xml_count': 0,
        'total_chats': 0,
        'errors': []
    }
    
    if xml3d_conversations_df.empty:
        validation_results['errors'].append("No customers in XML3D conversion")
        return validation_results
    
    # Check each customer's XML
    for _, row in xml3d_conversations_df.iterrows():
        xml_content = row.get('content_xml_view', '')
        chat_count = row.get('chat_count', 0)
        validation_results['total_chats'] += chat_count
        
        if not xml_content or xml_content.strip() == '':
            validation_results['empty_xml_count'] += 1
        else:
            # Basic XML structure validation
            if '<conversations>' in xml_content and '</conversations>' in xml_content:
                if '<chat_count>' in xml_content and '<chat>' in xml_content:
                    validation_results['valid_xml3d_count'] += 1
                else:
                    validation_results['errors'].append(f"Missing XML elements for customer {row.get('customer_name', 'unknown')}")
            else:
                validation_results['errors'].append(f"Invalid XML structure for customer {row.get('customer_name', 'unknown')}")
    
    validation_results['success_rate'] = (
        validation_results['valid_xml3d_count'] / validation_results['total_customers'] * 100
    ) if validation_results['total_customers'] > 0 else 0
    
    # Add expected keys for compatibility with processor
    validation_results['total_conversations'] = validation_results['total_customers']
    
    return validation_results


