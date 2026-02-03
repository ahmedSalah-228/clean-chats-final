"""
Clean Chats Integration Module
Provides easy-to-use functions for running clean chats analysis
"""

import sys
import os
from datetime import datetime, timedelta

# Add LLM_JUDGE to path for imports
llm_judge_path = "/Users/ahmedsalah/Projects/Clean Chats/LLM_JUDGE"
if llm_judge_path not in sys.path:
    sys.path.append(llm_judge_path)

from clean_chats_core import (
    analyze_department_clean_chats,
    analyze_all_departments_clean_chats
)
from clean_chats_storage import (
    save_clean_chats_summary,
    save_clean_chats_raw_data,
    get_clean_chats_summary_report,
    get_clean_chats_detail_report
)
from clean_chats_config import (
    list_all_clean_chats_departments,
    get_clean_chats_flagging_config
)

def run_clean_chats_analysis(session, target_date=None, save_to_database=True):
    """
    Run complete clean chats analysis for all departments
    
    Args:
        session: Snowflake session
        target_date: Target date for analysis (defaults to yesterday)
        save_to_database: Whether to save results to database tables
        
    Returns:
        Complete analysis results
    """
    print("\n🧹 RUNNING COMPLETE CLEAN CHATS ANALYSIS")
    print("=" * 60)
    
    # Set target date if not provided
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        # Run analysis for all departments
        results = analyze_all_departments_clean_chats(session, target_date)
        
        if save_to_database and results.get('department_results'):
            print("\n💾 SAVING RESULTS TO DATABASE")
            print("=" * 40)
            
            # Save summary data
            summary_success = save_clean_chats_summary(
                session, results['department_results'], target_date
            )
            
            # Save detailed data
            detail_success = save_clean_chats_raw_data(
                session, results['department_results'], target_date
            )
            
            results['database_save'] = {
                'summary_saved': summary_success,
                'details_saved': detail_success,
                'overall_success': summary_success and detail_success
            }
            
            if summary_success and detail_success:
                print("    ✅ All results saved to database successfully")
            else:
                print("    ⚠️  Some database save operations failed")
        
        return results
        
    except Exception as e:
        print(f"❌ Clean chats analysis failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'target_date': target_date
        }

def run_single_department_clean_chats(session, department_name, target_date=None, save_to_database=True):
    """
    Run clean chats analysis for a single department
    
    Args:
        session: Snowflake session
        department_name: Department to analyze
        target_date: Target date for analysis
        save_to_database: Whether to save results to database tables
        
    Returns:
        Single department analysis results
    """
    print(f"\n🧹 RUNNING CLEAN CHATS ANALYSIS: {department_name}")
    print("=" * 60)
    
    # Set target date if not provided
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        # Run analysis for single department
        results = analyze_department_clean_chats(session, department_name, target_date)
        
        if save_to_database and results.get('success'):
            print("\n💾 SAVING RESULTS TO DATABASE")
            print("=" * 40)
            
            # Wrap single department results for storage functions
            department_results = {department_name: results}
            
            # Save summary data
            summary_success = save_clean_chats_summary(
                session, department_results, target_date
            )
            
            # Save detailed data
            detail_success = save_clean_chats_raw_data(
                session, department_results, target_date
            )
            
            results['database_save'] = {
                'summary_saved': summary_success,
                'details_saved': detail_success,
                'overall_success': summary_success and detail_success
            }
            
            if summary_success and detail_success:
                print("    ✅ Results saved to database successfully")
            else:
                print("    ⚠️  Some database save operations failed")
        
        return results
        
    except Exception as e:
        print(f"❌ Clean chats analysis failed for {department_name}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'department': department_name,
            'target_date': target_date,
            'department_results': results
        }

def test_clean_chats_setup(session, department_name=None):
    """
    Test clean chats setup and configuration
    
    Args:
        session: Snowflake session
        department_name: Optional specific department to test
        
    Returns:
        Test results
    """
    print("\n🔍 TESTING CLEAN CHATS SETUP")
    print("=" * 50)
    
    test_results = {
        'configuration_test': {'status': 'PENDING'},
        'department_test': {'status': 'PENDING'},
        'database_test': {'status': 'PENDING'},
        'overall_status': 'PENDING'
    }
    
    try:
        # Test 1: Configuration
        print("🔧 Testing configuration...")
        departments = list_all_clean_chats_departments()
        flagging_config = get_clean_chats_flagging_config()
        
        test_results['configuration_test'] = {
            'status': 'SUCCESS',
            'departments_count': len(departments),
            'flagging_config_loaded': len(flagging_config) > 0,
            'departments': departments[:5]  # Show first 5
        }
        print(f"    ✅ Configuration test passed: {len(departments)} departments")
        
        # Test 2: Department analysis (small sample)
        print("🏢 Testing department analysis...")
        test_dept = department_name if department_name else 'CC_Resolvers'
        
        if test_dept in departments:
            # Use recent date for testing
            test_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            print(f"    Testing {test_dept} with date {test_date}...")
            result = analyze_department_clean_chats(session, test_dept, test_date)
            
            test_results['department_test'] = {
                'status': 'SUCCESS' if result.get('success') else 'FAILED',
                'department': test_dept,
                'conversations_analyzed': result.get('total_conversations', 0),
                'clean_percentage': result.get('clean_percentage', 0),
                'error': result.get('error')
            }
            
            if result.get('success'):
                print(f"    ✅ Department test passed: {result['total_conversations']} conversations analyzed")
            else:
                print(f"    ❌ Department test failed: {result.get('error', 'Unknown error')}")
        else:
            test_results['department_test'] = {
                'status': 'FAILED',
                'error': f'Department {test_dept} not found in configuration'
            }
            print(f"    ❌ Department {test_dept} not found")
        
        # Test 3: Database access
        print("🗄️  Testing database access...")
        try:
            # Test basic query
            test_query = "SELECT 1 as test_value"
            session.sql(test_query).collect()
            
            test_results['database_test'] = {
                'status': 'SUCCESS',
                'connection': 'OK',
                'query_execution': 'OK'
            }
            print("    ✅ Database test passed")
            
        except Exception as e:
            test_results['database_test'] = {
                'status': 'FAILED',
                'error': str(e)
            }
            print(f"    ❌ Database test failed: {str(e)}")
        
        # Determine overall status
        all_tests = [test_results['configuration_test'], test_results['department_test'], test_results['database_test']]
        if all(test['status'] == 'SUCCESS' for test in all_tests):
            test_results['overall_status'] = 'SUCCESS'
            print("\n🎉 ALL TESTS PASSED!")
        else:
            test_results['overall_status'] = 'FAILED'
            print("\n❌ SOME TESTS FAILED")
        
    except Exception as e:
        test_results['overall_status'] = 'ERROR'
        test_results['error'] = str(e)
        print(f"\n💥 TESTING ERROR: {str(e)}")
    
    return test_results

def get_clean_chats_report(session, target_date=None, department_filter=None, include_details=False):
    """
    Get clean chats report from database
    
    Args:
        session: Snowflake session
        target_date: Target date for report
        department_filter: Specific department filter
        include_details: Include detailed conversation data
        
    Returns:
        Report data
    """
    print("📊 GENERATING CLEAN CHATS REPORT")
    print("=" * 50)
    
    try:
        # Get summary report
        summary_data = get_clean_chats_summary_report(session, target_date, department_filter)
        
        report = {
            'summary': summary_data,
            'report_timestamp': datetime.now().isoformat(),
            'filters': {
                'target_date': target_date,
                'department_filter': department_filter
            }
        }
        
        if include_details:
            detail_data = get_clean_chats_detail_report(session, target_date, department_filter)
            report['details'] = detail_data
            print(f"    📋 Report includes {len(detail_data)} detailed records")
        
        print(f"    📊 Report generated with {len(summary_data)} summary records")
        return report
        
    except Exception as e:
        print(f"❌ Error generating report: {str(e)}")
        return {
            'error': str(e),
            'summary': [],
            'details': [] if include_details else None
        }

# Easy-use main functions
def main_clean_chats_analysis(session, target_date=None):
    """Main function for complete clean chats analysis"""
    return run_clean_chats_analysis(session, target_date)

def main_clean_chats_test(session, department_name=None):
    """Main function for clean chats testing"""
    return test_clean_chats_setup(session, department_name)

def main_clean_chats_report(session, target_date=None):
    """Main function for clean chats reporting"""
    return get_clean_chats_report(session, target_date, include_details=False)
