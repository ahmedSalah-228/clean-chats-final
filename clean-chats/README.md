# Clean Chats Analysis System

A post-pipeline analysis system that identifies "clean" conversations from the LLM_JUDGE processing results. Clean chats are conversations that passed through all department-specific LLM analysis prompts without being flagged for any issues.

## 🎯 **Project Purpose**

After the LLM_JUDGE pipeline completes its analysis, this system:

1. **Reads the same chat data** using identical filtering methods
2. **Checks flagging status** across all department-specific metric tables
3. **Identifies clean conversations** that weren't flagged by any analysis
4. **Generates insights** on conversation quality and issue distribution

## 🏗️ **Architecture Overview**

```
LLM_JUDGE Pipeline → Raw Metric Tables → Clean Chats Analysis → Clean/Flagged Classification
```

### **Clean Chat Definition**
A conversation is considered "clean" if:
- ✅ Processed through all department-specific prompts
- ✅ SA_prompt NPS score ≠ 1 (not poor sentiment)
- ✅ No specialized prompts contain "YES" responses (no issues detected)

### **Flagging Criteria**
A conversation is "flagged" if:
- ❌ SA_prompt returns NPS score = 1 (poor customer experience)
- ❌ Any specialized prompt LLM response contains "YES" (issue detected)

## 📁 **Project Structure**

```
clean-chats/
├── MAIN_CLEAN_CHATS.py          # Main Snowflake entry point
├── clean_chats_config.py        # Configuration and LLM_JUDGE integration
├── clean_chats_core.py          # Core analysis logic
├── clean_chats_storage.py       # Database storage and retrieval
├── clean_chats_integration.py   # Easy-use wrapper functions
└── README.md                    # This documentation
```

## 🔧 **Core Modules**

### **clean_chats_config.py**
- Imports LLM_JUDGE configurations
- Maps departments to their flagging tables
- Defines database schemas for results

### **clean_chats_core.py**
- Uses LLM_JUDGE Phase 1 filtering to get conversation IDs
- Checks each conversation against flagging criteria
- Calculates clean/flagged statistics

### **clean_chats_storage.py**
- Creates database tables for results
- Saves summary and detailed analysis data
- Provides reporting functions

### **clean_chats_integration.py**
- Wrapper functions for easy usage
- Testing and validation utilities
- Report generation

## 🚀 **Usage Examples**

### **1. Complete Analysis (All Departments)**
```python
from clean_chats_integration import main_clean_chats_analysis

def main(session):
    result = main_clean_chats_analysis(session, '2025-08-04')
    return result['summary']
```

### **2. Single Department Analysis**
```python
from clean_chats_integration import run_single_department_clean_chats

def main(session):
    result = run_single_department_clean_chats(session, 'MV_Resolvers', '2025-08-04')
    return f"Clean percentage: {result['clean_percentage']:.1f}%"
```

### **3. Testing Setup**
```python
from clean_chats_integration import main_clean_chats_test

def main(session):
    result = main_clean_chats_test(session, 'CC_Resolvers')
    return f"Test status: {result['overall_status']}"
```

### **4. Generate Reports**
```python
from clean_chats_integration import main_clean_chats_report

def main(session):
    result = main_clean_chats_report(session, '2025-08-04')
    return f"Found {len(result['summary'])} department summaries"
```

## 📊 **Output Tables**

### **CLEAN_CHATS_SUMMARY**
Department-level summary statistics:
- `DEPARTMENT`: Department name
- `TOTAL_CONVERSATIONS`: Total conversations analyzed
- `CLEAN_CONVERSATIONS`: Conversations with no flags
- `FLAGGED_CONVERSATIONS`: Conversations with issues
- `CLEAN_PERCENTAGE`: Percentage of clean conversations
- `FLAGGED_BY_SA_NPS`: Count flagged by poor sentiment (NPS=1)
- `FLAGGED_BY_SPECIALIZED_PROMPTS`: Count flagged by issue detection
- `FLAGGING_BREAKDOWN`: JSON breakdown of flagging sources

### **CLEAN_CHATS_DETAIL**
Conversation-level detailed results:
- `CONVERSATION_ID`: Unique conversation identifier
- `CUSTOMER_NAME`: Customer name from conversation
- `AGENT_NAMES`: Agent(s) who handled the conversation
- `IS_CLEAN`: Boolean indicating if conversation is clean
- `FLAGGING_SOURCES`: Sources that flagged the conversation
- `FLAGGING_DETAILS`: JSON details of flagging criteria

## 🏢 **Department-Specific Logic**

### **CC_Resolvers (Customer Care)**
- **Flagging Sources**: SA_RAW_DATA (NPS=1)
- **Clean Focus**: Basic customer satisfaction

### **MV_Resolvers (Maid Visa) - Most Complex**
- **Flagging Sources**: 13+ tables including:
  - SA_RAW_DATA (sentiment)
  - CLIENT_SUSPECTING_AI_RAW_DATA (AI detection)
  - FALSE_PROMISES_RAW_DATA (promise fulfillment)
  - THREATENING_RAW_DATA (threat detection)
  - POLICY_ESCALATION_RAW_DATA (policy violations)
  - And 8+ more specialized tables

### **Doctors (Medical Services)**
- **Flagging Sources**: Medical-specific tables:
  - SA_RAW_DATA (sentiment)
  - DOCTORS_MISPRESCRIPTION_RAW_DATA (prescription accuracy)
  - DOCTORS_UNNECESSARY_CLINIC_RAW_DATA (clinic recommendations)
  - Medical policy and clarity tables

### **AT_Filipina (Filipino Applicants)**
- **Flagging Sources**: Applicant journey tables:
  - SA_RAW_DATA (sentiment)
  - LOSS_INTEREST_RAW_DATA (retention issues)
  - POLICY_VIOLATION_RAW_DATA (process compliance)

## 🔍 **Key Features**

### **1. Same Data Foundation**
- Uses identical filtering logic as LLM_JUDGE
- Ensures consistency with original analysis
- Processes exact same conversation set

### **2. Comprehensive Flagging**
- Checks all department-specific prompt results
- Dual criteria: sentiment (NPS=1) + issue detection ("YES")
- Detailed breakdown of flagging sources

### **3. Flexible Analysis**
- Single department or all departments
- Historical date analysis
- Detailed and summary reporting

### **4. Database Integration**
- Automatic table creation
- Summary and detail storage
- Report generation from stored data

## 📈 **Sample Analysis Output**

```
🧹 CLEAN CHATS ANALYSIS - SUMMARY
==================================================
📅 Date: 2025-08-04
🏢 Departments processed: 9/9
✅ Successful departments: 9/9

📊 OVERALL METRICS:
   💬 Total conversations: 15,423
   ✅ Clean conversations: 12,841 (83.3%)
   🚩 Flagged conversations: 2,582 (16.7%)

🌟 Clean Chats Analysis Complete!
   Ready for review and reporting
```

## 🔧 **Dependencies**

### **LLM_JUDGE Integration**
- Imports configurations from LLM_JUDGE project
- Uses Phase 1 filtering logic
- Accesses same Snowflake tables and schemas

### **Required Modules**
- `snowflake.snowpark`: Snowflake integration
- `pandas`: Data manipulation
- `json`: JSON processing
- `datetime`: Date handling

## 🏃‍♂️ **Quick Start**

1. **Upload to Snowflake**: Upload all Python files to your Snowflake environment

2. **Run Analysis**: Execute `MAIN_CLEAN_CHATS.py` with your target date

3. **Check Results**: Query `CLEAN_CHATS_SUMMARY` and `CLEAN_CHATS_DETAIL` tables

4. **Generate Reports**: Use integration functions for custom reporting

## 🎯 **Business Value**

### **Quality Insights**
- Measure conversation quality across departments
- Identify departments with highest/lowest clean rates
- Track quality trends over time

### **Issue Distribution**
- Understand which prompts flag conversations most
- Differentiate sentiment issues vs. specialized problems
- Guide training and process improvements

### **Performance Metrics**
- Complement LLM_JUDGE flagging analysis
- Provide positive quality indicators
- Support quality assurance processes

This system provides the "other side" of LLM_JUDGE analysis - instead of just identifying issues, it celebrates and tracks conversations that meet quality standards across all evaluation criteria.
