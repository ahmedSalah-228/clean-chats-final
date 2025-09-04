# The Snowpark package is required for Python Worksheets. 
# You can add more packages by selecting them using the Packages control and then importing them.

import snowflake.snowpark as snowpark
from snowflake.snowpark.functions import col
from snowflake_llm_integration import (
    validate_llm_setup,
    test_llm_analysis, 
    check_llm_status,
    run_llm_analysis
)

def main(session: snowpark.Session):
    # Step 1: Quick test with single department
    test_result = test_llm_analysis(session, 'MV_Resolvers', '2025-08-04')
    if test_result['success']:
        return f"✅ Test passed! Ready for full analysis."
    else:
        return f"❌ Test failed: {test_result.get('error', 'Unknown')}"
