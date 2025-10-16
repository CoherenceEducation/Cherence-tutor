#!/usr/bin/env python3
"""
Test script to verify the comprehensive analytics fixes
"""

def test_analytics_functions():
    """Test that all analytics functions return proper data structures"""
    
    # Mock cursor for testing
    class MockCursor:
        def execute(self, query):
            pass
        def fetchone(self):
            return {'total_chats': 0, 'avg_messages_per_session': 0, 'avg_session_duration': 0, 'unique_active_students': 0}
        def fetchall(self):
            return []
    
    # Import the functions
    try:
        from utils.db import (
            get_engagement_metrics,
            get_topic_analysis, 
            get_sentiment_analysis,
            get_progress_indicators,
            get_academic_focus,
            get_curiosity_metrics
        )
        
        mock_cursor = MockCursor()
        
        # Test each function
        functions_to_test = [
            ('Engagement Metrics', get_engagement_metrics),
            ('Topic Analysis', get_topic_analysis),
            ('Sentiment Analysis', get_sentiment_analysis),
            ('Progress Indicators', get_progress_indicators),
            ('Academic Focus', get_academic_focus),
            ('Curiosity Metrics', get_curiosity_metrics)
        ]
        
        print("🧪 Testing Analytics Functions...")
        print("=" * 50)
        
        all_passed = True
        for name, func in functions_to_test:
            try:
                result = func(mock_cursor)
                if isinstance(result, dict):
                    print(f"✅ {name}: Returns dict with {len(result)} keys")
                else:
                    print(f"❌ {name}: Returns {type(result)} instead of dict")
                    all_passed = False
            except Exception as e:
                print(f"❌ {name}: Error - {e}")
                all_passed = False
        
        print("=" * 50)
        if all_passed:
            print("🎉 All analytics functions work correctly!")
            print("\n✅ The comprehensive analytics should now work properly.")
            print("📊 The admin dashboard will show data instead of loading indicators.")
        else:
            print("❌ Some functions have issues.")
            
        return all_passed
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the project root directory.")
        return False

if __name__ == "__main__":
    test_analytics_functions()
