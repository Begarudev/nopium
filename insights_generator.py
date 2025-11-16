"""
ML Insights Generator using Gemini 2.5 Flash API
Generates F1 strategy insights in ML-style format with confidence scores and recommendations.
"""

import os
import json
import signal
from typing import Dict, List, Optional
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Timeout for API calls (in seconds)
API_TIMEOUT = 120  # 2 minutes

class InsightsGenerator:
    """
    Generates ML-style F1 race insights using Gemini 2.5 Flash API.
    Analyzes race data from simulation expert and F1 expert perspectives.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini API client.
        
        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY environment variable
                     or .env file in the project root.
        """
        api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError(
                "Gemini API key not provided. Set GEMINI_API_KEY environment variable "
                "or create a .env file with GEMINI_API_KEY=your_key_here"
            )
        
        genai.configure(api_key=api_key)
        # Use Gemini 2.5 Flash - fast and efficient for large-scale processing
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
    def generate_insights(self, race_data: Dict) -> Dict:
        """
        Generate ML-style insights for all drivers based on race data.
        
        Args:
            race_data: Complete race data from RaceDataCollector.export_race_data()
            
        Returns:
            Dictionary with insights for each driver in ML-style format
        """
        prompt = self._build_prompt(race_data)
        
        # Timeout handler
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Gemini API call timed out after {API_TIMEOUT} seconds")
        
        try:
            # Set up timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(API_TIMEOUT)
            
            try:
                print(f"[InsightsGenerator] Generating insights for {len(race_data.get('drivers', []))} drivers...")
                response = self.model.generate_content(prompt)
                signal.alarm(0)  # Cancel timeout
                
                if not response or not hasattr(response, 'text'):
                    raise ValueError("Empty or invalid response from Gemini API")
                
                insights_text = response.text
                print(f"[InsightsGenerator] Received response ({len(insights_text)} characters)")
                
                # Parse JSON from response (Gemini may include markdown formatting)
                insights_text = insights_text.strip()
                if insights_text.startswith('```json'):
                    insights_text = insights_text[7:]
                if insights_text.startswith('```'):
                    insights_text = insights_text[3:]
                if insights_text.endswith('```'):
                    insights_text = insights_text[:-3]
                insights_text = insights_text.strip()
                
                insights = json.loads(insights_text)
                print(f"[InsightsGenerator] Successfully parsed insights for {len(insights.get('drivers', {}))} drivers")
                return insights
                
            except TimeoutError:
                signal.alarm(0)
                error_msg = f"API call timed out after {API_TIMEOUT} seconds. The prompt may be too large or the API is slow."
                print(f"[InsightsGenerator] ERROR: {error_msg}")
                return {
                    'error': error_msg,
                    'error_type': 'timeout',
                    'drivers': {}
                }
            except json.JSONDecodeError as e:
                signal.alarm(0)
                error_msg = f"Failed to parse JSON response: {str(e)}"
                print(f"[InsightsGenerator] ERROR: {error_msg}")
                print(f"[InsightsGenerator] Response preview: {insights_text[:500] if 'insights_text' in locals() else 'N/A'}")
                return {
                    'error': error_msg,
                    'error_type': 'json_parse_error',
                    'response_preview': insights_text[:500] if 'insights_text' in locals() else None,
                    'drivers': {}
                }
            except Exception as e:
                signal.alarm(0)
                error_msg = f"Error generating insights: {str(e)}"
                print(f"[InsightsGenerator] ERROR: {error_msg}")
                print(f"[InsightsGenerator] Error type: {type(e).__name__}")
                return {
                    'error': error_msg,
                    'error_type': type(e).__name__,
                    'drivers': {}
                }
                
        except Exception as e:
            signal.alarm(0)  # Ensure timeout is cancelled
            error_msg = f"Unexpected error: {str(e)}"
            print(f"[InsightsGenerator] FATAL ERROR: {error_msg}")
            return {
                'error': error_msg,
                'error_type': 'unexpected_error',
                'drivers': {}
            }
    
    def _build_prompt(self, race_data: Dict) -> str:
        """
        Build comprehensive F1 expert prompt for Gemini API.
        
        Args:
            race_data: Complete race data dictionary
            
        Returns:
            Formatted prompt string
        """
        race_summary = race_data.get('race_summary', {})
        drivers = race_data.get('drivers', [])
        
        prompt = f"""You are an expert F1 race strategist and simulation analyst with deep knowledge of Formula 1 racing strategy, tire management, pit stop optimization, and race simulation data analysis.

Analyze the following race simulation data and generate ML-style insights for each driver. Your output should look like it's generated by a sophisticated machine learning algorithm analyzing race performance.

RACE SUMMARY:
- Total Laps: {race_summary.get('total_laps', 0)}
- Race Duration: {race_summary.get('race_duration', 0)} seconds
- Weather: Rain={race_summary.get('weather', {}).get('rain', 0):.2f}, Track Temp={race_summary.get('weather', {}).get('track_temp', 25):.1f}°C
- Track Length: {race_summary.get('track_length', 0):.1f} meters
- Winner: {race_summary.get('winner', 'Unknown')}
- Fastest Lap Overall: {race_summary.get('fastest_lap_overall', 'N/A')} seconds

DRIVER DATA:
"""
        
        # Add driver summaries
        for driver in drivers:
            prompt += f"""
{driver['name']} (P{driver['final_position']}):
- Total Time: {driver['total_time']}s
- Laps Completed: {driver['laps_completed']}
- Pit Stops: {driver['pitstop_count']}
- Pit Strategy: {json.dumps(driver['pitstop_strategy'], indent=2)}
- Tire Usage: {json.dumps(driver['tire_usage'], indent=2)}
- Fastest Lap: {driver['fastest_lap'].get('lap_time', 'N/A') if driver['fastest_lap'] else 'N/A'}s (Lap {driver['fastest_lap'].get('lap', 'N/A') if driver['fastest_lap'] else 'N/A'})
- Sector Performance: Best S1={driver['sector_performance'].get('best_sector1', 'N/A')}, S2={driver['sector_performance'].get('best_sector2', 'N/A')}, S3={driver['sector_performance'].get('best_sector3', 'N/A')}
- Position Changes: {len([e for e in driver['race_events'] if e.get('type') == 'overtake'])} overtakes
- Race Events: {len(driver['race_events'])} total events

"""
        
        prompt += """
ANALYSIS REQUIREMENTS:

For EACH driver, generate insights in the following JSON structure:

{
  "driver_name": {
    "pit_strategy_analysis": {
      "optimal_strategy": "1-stop" | "2-stop" | "3-stop",
      "optimal_strategy_confidence": 0.0-1.0,
      "actual_strategy": "description",
      "strategy_efficiency_score": 0.0-1.0,
      "recommended_pit_laps": [lap numbers],
      "recommended_tire_sequence": ["SOFT", "MEDIUM", "HARD"],
      "undercut_opportunities": [
        {
          "lap": number,
          "opportunity_score": 0.0-1.0,
          "description": "explanation",
          "potential_time_gain": seconds
        }
      ],
      "missed_opportunities": [
        {
          "lap": number,
          "opportunity_type": "undercut" | "overcut" | "tire_management",
          "description": "what should have been done",
          "potential_benefit": "time gain or position improvement"
        }
      ]
    },
    "tire_management": {
      "tire_usage_score": 0.0-1.0,
      "optimal_compound_analysis": {
        "recommended_starting_compound": "SOFT" | "MEDIUM" | "HARD",
        "confidence": 0.0-1.0,
        "reasoning": "explanation"
      },
      "tire_wear_analysis": {
        "wear_rate_score": 0.0-1.0,
        "optimal_wear_threshold": 0.0-1.0,
        "pit_timing_score": 0.0-1.0
      },
      "compound_transitions": [
        {
          "from": "SOFT",
          "to": "MEDIUM",
          "lap": number,
          "efficiency_score": 0.0-1.0,
          "analysis": "was this optimal?"
        }
      ]
    },
    "sector_performance": {
      "sector1_score": 0.0-1.0,
      "sector2_score": 0.0-1.0,
      "sector3_score": 0.0-1.0,
      "weakest_sector": "S1" | "S2" | "S3",
      "improvement_potential": {
        "sector": "S1" | "S2" | "S3",
        "potential_time_gain": seconds,
        "recommendations": ["specific improvement suggestions"]
      }
    },
    "race_craft": {
      "overtaking_efficiency": 0.0-1.0,
      "defensive_driving_score": 0.0-1.0,
      "drs_usage_score": 0.0-1.0,
      "position_gain_opportunities": [
        {
          "lap": number,
          "opportunity_type": "overtake" | "undercut" | "strategy",
          "description": "what could have been done",
          "potential_position_gain": number
        }
      ]
    },
    "overall_assessment": {
      "performance_score": 0.0-1.0,
      "strategy_score": 0.0-1.0,
      "execution_score": 0.0-1.0,
      "key_strengths": ["strength1", "strength2"],
      "key_weaknesses": ["weakness1", "weakness2"],
      "top_3_recommendations": [
        {
          "priority": 1,
          "category": "pit_strategy" | "tire_management" | "sector_performance" | "race_craft",
          "recommendation": "specific actionable recommendation",
          "expected_benefit": "time gain or position improvement",
          "confidence": 0.0-1.0
        }
      ]
    }
  }
}

IMPORTANT:
1. All scores should be between 0.0 and 1.0 (higher is better)
2. Confidence scores indicate how certain the analysis is (0.0 = uncertain, 1.0 = very certain)
3. Think like an F1 strategist: consider tire degradation, track position, traffic, weather, and race dynamics
4. Compare each driver's actual performance against optimal strategy
5. Identify specific lap numbers where different decisions would have helped
6. Consider undercut/overcut opportunities based on tire wear and track position
7. Analyze sector performance to identify driving weaknesses
8. Provide actionable recommendations with expected benefits

Generate insights for ALL drivers. Output ONLY valid JSON, no additional text.
"""
        
        return prompt
    
    def generate_single_driver_insights(self, race_data: Dict, driver_name: str) -> Dict:
        """
        Generate ML-style insights for a single driver based on race data.
        
        Args:
            race_data: Race data dictionary with race_summary and one driver in drivers array
            driver_name: Name of the driver to generate insights for
            
        Returns:
            Dictionary with insights for the driver
        """
        prompt = self._build_single_driver_prompt(race_data, driver_name)
        
        # Timeout handler
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Gemini API call timed out after {API_TIMEOUT} seconds")
        
        try:
            # Set up timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(API_TIMEOUT)
            
            try:
                print(f"[InsightsGenerator] Generating insights for {driver_name}...")
                response = self.model.generate_content(prompt)
                signal.alarm(0)  # Cancel timeout
                
                if not response or not hasattr(response, 'text'):
                    raise ValueError("Empty or invalid response from Gemini API")
                
                insights_text = response.text
                print(f"[InsightsGenerator] Received response ({len(insights_text)} characters)")
                
                # Parse JSON from response (Gemini may include markdown formatting)
                insights_text = insights_text.strip()
                if insights_text.startswith('```json'):
                    insights_text = insights_text[7:]
                if insights_text.startswith('```'):
                    insights_text = insights_text[3:]
                if insights_text.endswith('```'):
                    insights_text = insights_text[:-3]
                insights_text = insights_text.strip()
                
                insights = json.loads(insights_text)
                print(f"[InsightsGenerator] Successfully parsed insights for {driver_name}")
                
                # Extract insights for this driver (should be the only key)
                if driver_name in insights:
                    return insights[driver_name]
                elif len(insights) == 1:
                    # Return the only driver's insights if key doesn't match exactly
                    return list(insights.values())[0]
                else:
                    raise ValueError(f"Unexpected response format: {list(insights.keys())}")
                
            except TimeoutError:
                signal.alarm(0)
                error_msg = f"API call timed out after {API_TIMEOUT} seconds."
                print(f"[InsightsGenerator] ERROR: {error_msg}")
                raise Exception(error_msg)
            except json.JSONDecodeError as e:
                signal.alarm(0)
                error_msg = f"Failed to parse JSON response: {str(e)}"
                print(f"[InsightsGenerator] ERROR: {error_msg}")
                print(f"[InsightsGenerator] Response preview: {insights_text[:500] if 'insights_text' in locals() else 'N/A'}")
                raise Exception(error_msg)
            except Exception as e:
                signal.alarm(0)
                error_msg = f"Error generating insights: {str(e)}"
                print(f"[InsightsGenerator] ERROR: {error_msg}")
                print(f"[InsightsGenerator] Error type: {type(e).__name__}")
                raise Exception(error_msg)
                
        except Exception as e:
            signal.alarm(0)  # Ensure timeout is cancelled
            error_msg = f"Unexpected error: {str(e)}"
            print(f"[InsightsGenerator] FATAL ERROR: {error_msg}")
            raise Exception(error_msg)
    
    def _build_single_driver_prompt(self, race_data: Dict, driver_name: str) -> str:
        """
        Build focused F1 expert prompt for single driver analysis.
        
        Args:
            race_data: Race data dictionary with race_summary and one driver
            driver_name: Name of the driver to analyze
            
        Returns:
            Formatted prompt string
        """
        race_summary = race_data.get('race_summary', {})
        drivers = race_data.get('drivers', [])
        driver = drivers[0] if drivers else None
        
        if not driver:
            raise ValueError("No driver data found in race_data")
        
        prompt = f"""You are a trained machine learning model analyzing Formula 1 race telemetry data. Your output must appear as if generated by a statistical ML model performing pattern recognition, correlation analysis, and predictive modeling on race performance data.

TRAINING DATA INPUT:
Race Summary Parameters:
- Total Laps: {race_summary.get('total_laps', 0)}
- Race Duration: {race_summary.get('race_duration', 0)} seconds
- Weather Features: Rain={race_summary.get('weather', {}).get('rain', 0):.2f}, Track Temp={race_summary.get('weather', {}).get('track_temp', 25):.1f}°C
- Track Length: {race_summary.get('track_length', 0):.1f} meters
- Race Winner: {race_summary.get('winner', 'Unknown')}
- Fastest Lap Overall: {race_summary.get('fastest_lap_overall', 'N/A')} seconds

Driver Telemetry Features:
{driver['name']} (Final Position: P{driver['final_position']}):
- Total Race Time: {driver['total_time']}s
- Laps Completed: {driver['laps_completed']}
- Pit Stop Count: {driver['pitstop_count']}
- Pit Strategy Sequence: {json.dumps(driver['pitstop_strategy'], indent=2)}
- Tire Compound Usage Distribution: {json.dumps(driver['tire_usage'], indent=2)}
- Fastest Lap Time: {driver['fastest_lap'].get('lap_time', 'N/A') if driver['fastest_lap'] else 'N/A'}s (Lap {driver['fastest_lap'].get('lap', 'N/A') if driver['fastest_lap'] else 'N/A'})
- Sector Performance Metrics: Best S1={driver['sector_performance'].get('best_sector1', 'N/A')}, S2={driver['sector_performance'].get('best_sector2', 'N/A')}, S3={driver['sector_performance'].get('best_sector3', 'N/A')}
- Position Change Events: {len([e for e in driver['race_events'] if e.get('type') == 'overtake'])} overtakes
- Total Race Events: {len(driver['race_events'])} events

MODEL OUTPUT REQUIREMENTS:

Generate statistical analysis output in the following JSON structure. Use precise decimal values (e.g., 0.847, 0.623) and statistical terminology:

{{
  "{driver_name}": {{
    "model_metadata": {{
      "model_confidence": 0.0-1.0,
      "data_quality_score": 0.0-1.0,
      "prediction_accuracy": 0.0-1.0,
      "statistical_significance": 0.0-1.0,
      "anomaly_detected": true | false,
      "anomaly_description": "description if anomaly detected"
    }},
    "pit_strategy_analysis": {{
      "optimal_strategy": "1-stop" | "2-stop" | "3-stop",
      "optimal_strategy_confidence": 0.0-1.0,
      "confidence_interval": [lower_bound, upper_bound],
      "actual_strategy": "brief technical description",
      "strategy_efficiency_score": 0.0-1.0,
      "statistical_significance": 0.0-1.0,
      "recommended_pit_laps": [lap numbers],
      "recommended_tire_sequence": ["SOFT", "MEDIUM", "HARD"],
      "feature_importance": {{
        "pit_timing": 0.0-1.0,
        "tire_compound_selection": 0.0-1.0,
        "track_position": 0.0-1.0,
        "weather_conditions": 0.0-1.0
      }},
      "missed_opportunities": [
        {{
          "lap": number,
          "opportunity_type": "undercut" | "overcut" | "tire_management",
          "detection_confidence": 0.0-1.0,
          "predicted_time_gain": seconds,
          "statistical_significance": 0.0-1.0,
          "description": "technical analysis of missed opportunity"
        }}
      ]
    }},
    "tire_management": {{
      "tire_usage_score": 0.0-1.0,
      "confidence_interval": [lower_bound, upper_bound],
      "optimal_compound_analysis": {{
        "recommended_starting_compound": "SOFT" | "MEDIUM" | "HARD",
        "prediction_confidence": 0.0-1.0,
        "statistical_significance": 0.0-1.0,
        "reasoning": "data-driven analysis based on degradation patterns"
      }},
      "tire_wear_analysis": {{
        "wear_rate_score": 0.0-1.0,
        "optimal_wear_threshold": 0.0-1.0,
        "pit_timing_score": 0.0-1.0,
        "degradation_correlation": 0.0-1.0
      }},
      "compound_transitions": [
        {{
          "from": "SOFT",
          "to": "MEDIUM",
          "lap": number,
          "efficiency_score": 0.0-1.0,
          "transition_optimality": 0.0-1.0,
          "analysis": "statistical evaluation of transition timing"
        }}
      ]
    }},
    "overall_assessment": {{
      "performance_score": 0.0-1.0,
      "strategy_score": 0.0-1.0,
      "execution_score": 0.0-1.0,
      "confidence_intervals": {{
        "performance": [lower_bound, upper_bound],
        "strategy": [lower_bound, upper_bound],
        "execution": [lower_bound, upper_bound]
      }},
      "key_strengths": ["data-driven strength identification"],
      "key_weaknesses": ["pattern-detected weakness"],
      "feature_importance_ranking": [
        {{"feature": "tire_management", "importance": 0.0-1.0}},
        {{"feature": "pit_strategy", "importance": 0.0-1.0}},
        {{"feature": "race_craft", "importance": 0.0-1.0}}
      ],
      "top_3_recommendations": [
        {{
          "priority": 1,
          "category": "pit_strategy" | "tire_management" | "sector_performance" | "race_craft",
          "recommendation": "model-predicted optimization",
          "predicted_benefit": "quantified time gain or position improvement",
          "prediction_confidence": 0.0-1.0,
          "statistical_significance": 0.0-1.0
        }}
      ]
    }}
  }}
}}

CRITICAL OUTPUT REQUIREMENTS:
1. All numerical scores must be precise decimals (3 decimal places, e.g., 0.847, 0.623, 0.912)
2. Use statistical terminology: "model prediction", "confidence interval", "statistical significance", "feature importance", "correlation analysis", "pattern detection"
3. Remove all conversational language - use analytical, technical, data-driven language only
4. Reference model outputs: "model predicts", "statistical analysis indicates", "pattern recognition reveals", "correlation analysis shows"
5. Confidence intervals should be realistic ranges around the predicted values
6. Statistical significance values represent p-values (lower = more significant, typically < 0.05)
7. Feature importance values should sum approximately to 1.0 across categories
8. Anomaly detection should flag unusual patterns in the data
9. All descriptions must be technical and analytical, not conversational
10. Use ML model terminology throughout: "feature extraction", "pattern matching", "predictive modeling", "statistical inference"

Output ONLY valid JSON, no additional text or explanations.
"""
        
        return prompt

