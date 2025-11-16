import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Award, TrendingUp, AlertCircle, CheckCircle, RotateCcw, ArrowLeft, Trophy, Zap, Loader2 } from 'lucide-react';
import './RaceDashboard.css';

const RaceDashboard = ({ 
  insights = {}, 
  undercutSummary = [], 
  raceState = {},
  onReset,
  onBack
}) => {
  const [generatingInsights, setGeneratingInsights] = useState({});
  const [mlInsights, setMlInsights] = useState({});

  // Sort insights by final position (P1, P2, etc.)
  const sortedInsights = Object.values(insights).sort((a, b) => {
    return (a.final_position || 999) - (b.final_position || 999);
  });

  const handleGenerateDriverInsight = async (driverName) => {
    setGeneratingInsights(prev => ({ ...prev, [driverName]: true }));
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/driver-insight/${encodeURIComponent(driverName)}`,
        { method: 'POST' }
      );
      
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.insights) {
          setMlInsights(prev => ({
            ...prev,
            [driverName]: data.insights
          }));
        } else {
          console.error('Failed to generate insights:', data.error);
        }
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('Failed to generate insights:', errorData.detail || 'Unknown error');
      }
    } catch (error) {
      console.error('Error generating insights:', error);
    } finally {
      setGeneratingInsights(prev => ({ ...prev, [driverName]: false }));
    }
  };

  const getInsightIcon = (type) => {
    switch (type) {
      case 'undercut_success':
      case 'position_gain':
        return <CheckCircle size={16} className="insight-icon success" />;
      case 'undercut_failure':
      case 'position_loss':
        return <AlertCircle size={16} className="insight-icon warning" />;
      default:
        return <Award size={16} className="insight-icon" />;
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="race-dashboard">
      <div className="race-dashboard-header">
        <div className="dashboard-title-section">
          <Trophy size={32} className="dashboard-trophy-icon" />
          <div>
            <h1>Race Complete</h1>
            <p className="dashboard-subtitle">Post-Race Analysis & Insights</p>
          </div>
        </div>
        <div className="dashboard-actions">
          {onBack && (
            <button className="back-button" onClick={onBack}>
              <ArrowLeft size={18} />
              Back to Race
            </button>
          )}
          {onReset && (
            <button className="reset-button" onClick={onReset}>
              <RotateCcw size={18} />
              Reset Race
            </button>
          )}
        </div>
      </div>

      <div className="race-dashboard-content">
        {/* Undercut Analysis Section */}
        {undercutSummary && undercutSummary.length > 0 && (
          <motion.section
            className="dashboard-section undercut-section"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="section-header">
              <Award size={24} />
              <h2>Undercut Analysis</h2>
            </div>
            <div className="undercut-grid">
              {undercutSummary.map((pitstop, idx) => (
                <motion.div
                  key={idx}
                  className="undercut-card"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: idx * 0.1 }}
                >
                  <div className="undercut-card-header">
                    <div>
                      <strong className="undercut-driver-name">{pitstop.car}</strong>
                      <span className="undercut-lap">Lap {pitstop.lap}</span>
                    </div>
                    <div className="undercut-tyre-change">
                      <span className="tyre-badge old">{pitstop.old_tyre}</span>
                      <span className="tyre-arrow">→</span>
                      <span className="tyre-badge new">{pitstop.new_tyre}</span>
                    </div>
                  </div>
                  <div className="undercut-card-body">
                    <div className="pit-time-info">
                      Pit Time: <strong>{pitstop.pit_time}s</strong>
                    </div>
                    <div className="undercut-list">
                      {pitstop.undercuts.map((undercut, uIdx) => (
                        <div key={uIdx} className="undercut-item">
                          <span className={`undercut-time ${undercut.time_gain > 0 ? 'gain' : 'loss'}`}>
                            {undercut.time_gain > 0 ? '+' : ''}{undercut.time_gain.toFixed(2)}s
                          </span>
                          <span className="undercut-vs">vs {undercut.vs}</span>
                          {undercut.position_change !== 0 && (
                            <span className="undercut-position">
                              (P{undercut.position_before} → P{undercut.position_after})
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.section>
        )}

        {/* Driver Insights Section */}
        <motion.section
          className="dashboard-section insights-section"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div className="section-header">
            <TrendingUp size={24} />
            <h2>Driver Insights</h2>
          </div>
          <div className="insights-grid">
            {sortedInsights.map((driver, idx) => (
              <motion.div
                key={driver.name}
                className="driver-insight-card"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
              >
                <div className="driver-card-header">
                  <div className="driver-card-title">
                    <span className="driver-position-badge">P{driver.final_position}</span>
                    <h3>{driver.name}</h3>
                  </div>
                  <div className="driver-header-right">
                    <div className="driver-stats-mini">
                      <div className="mini-stat">
                        <span className="mini-stat-label">Time</span>
                        <span className="mini-stat-value">{formatTime(driver.total_time)}</span>
                      </div>
                      <div className="mini-stat">
                        <span className="mini-stat-label">Pitstops</span>
                        <span className="mini-stat-value">{driver.pitstops}</span>
                      </div>
                    </div>
                    <button
                      className="generate-insight-btn"
                      onClick={() => handleGenerateDriverInsight(driver.name)}
                      disabled={generatingInsights[driver.name]}
                    >
                      {generatingInsights[driver.name] ? (
                        <>
                          <Loader2 className="spinning-loader" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Zap size={14} />
                          Generate ML Insight
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {driver.insights && driver.insights.length > 0 && (
                  <div className="driver-insights-list">
                    <h4 className="insights-subheader">
                      <TrendingUp size={16} />
                      Key Insights
                    </h4>
                    {driver.insights.map((insight, iIdx) => (
                      <div key={iIdx} className="insight-item">
                        {getInsightIcon(insight.type)}
                        <div className="insight-content">
                          <div className="insight-message">{insight.message}</div>
                          <div className="insight-action">{insight.action}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {driver.recommendations && driver.recommendations.length > 0 && (
                  <div className="driver-recommendations-list">
                    <h4 className="recommendations-subheader">
                      <AlertCircle size={16} />
                      Recommendations
                    </h4>
                    <ul className="recommendations-list">
                      {driver.recommendations.map((rec, rIdx) => (
                        <li key={rIdx} className="recommendation-item">{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {mlInsights[driver.name] && (
                  <div className="ml-insights-section">
                    <h4 className="insights-subheader">
                      <Zap size={16} />
                      ML Model Predictions
                    </h4>
                    
                    {mlInsights[driver.name].model_metadata && (
                      <div className="ml-model-metadata">
                        <div className="ml-metadata-row">
                          <span className="ml-metadata-label">Model Confidence:</span>
                          <span className="ml-metadata-value">
                            {((mlInsights[driver.name].model_metadata.model_confidence || 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="ml-metadata-row">
                          <span className="ml-metadata-label">Data Quality:</span>
                          <span className="ml-metadata-value">
                            {((mlInsights[driver.name].model_metadata.data_quality_score || 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="ml-metadata-row">
                          <span className="ml-metadata-label">Prediction Accuracy:</span>
                          <span className="ml-metadata-value">
                            {((mlInsights[driver.name].model_metadata.prediction_accuracy || 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                        {mlInsights[driver.name].model_metadata.anomaly_detected && (
                          <div className="ml-anomaly-alert">
                            <AlertCircle size={14} />
                            <span>Anomaly Detected: {mlInsights[driver.name].model_metadata.anomaly_description || 'Unusual pattern detected'}</span>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {mlInsights[driver.name].overall_assessment && (
                      <div className="ml-overall-assessment">
                        <div className="ml-scores">
                          <div className="ml-score-item">
                            <span className="ml-score-label">Performance</span>
                            <span className="ml-score-value">
                              {((mlInsights[driver.name].overall_assessment.performance_score || 0) * 100).toFixed(1)}%
                            </span>
                            {mlInsights[driver.name].overall_assessment.confidence_intervals?.performance && (
                              <span className="ml-confidence-interval">
                                [{((mlInsights[driver.name].overall_assessment.confidence_intervals.performance[0] || 0) * 100).toFixed(1)}%, 
                                {((mlInsights[driver.name].overall_assessment.confidence_intervals.performance[1] || 0) * 100).toFixed(1)}%]
                              </span>
                            )}
                          </div>
                          <div className="ml-score-item">
                            <span className="ml-score-label">Strategy</span>
                            <span className="ml-score-value">
                              {((mlInsights[driver.name].overall_assessment.strategy_score || 0) * 100).toFixed(1)}%
                            </span>
                            {mlInsights[driver.name].overall_assessment.confidence_intervals?.strategy && (
                              <span className="ml-confidence-interval">
                                [{((mlInsights[driver.name].overall_assessment.confidence_intervals.strategy[0] || 0) * 100).toFixed(1)}%, 
                                {((mlInsights[driver.name].overall_assessment.confidence_intervals.strategy[1] || 0) * 100).toFixed(1)}%]
                              </span>
                            )}
                          </div>
                          <div className="ml-score-item">
                            <span className="ml-score-label">Execution</span>
                            <span className="ml-score-value">
                              {((mlInsights[driver.name].overall_assessment.execution_score || 0) * 100).toFixed(1)}%
                            </span>
                            {mlInsights[driver.name].overall_assessment.confidence_intervals?.execution && (
                              <span className="ml-confidence-interval">
                                [{((mlInsights[driver.name].overall_assessment.confidence_intervals.execution[0] || 0) * 100).toFixed(1)}%, 
                                {((mlInsights[driver.name].overall_assessment.confidence_intervals.execution[1] || 0) * 100).toFixed(1)}%]
                              </span>
                            )}
                          </div>
                        </div>
                        
                        {mlInsights[driver.name].overall_assessment.feature_importance_ranking && 
                         mlInsights[driver.name].overall_assessment.feature_importance_ranking.length > 0 && (
                          <div className="ml-feature-importance">
                            <strong>Feature Importance:</strong>
                            <div className="ml-feature-list">
                              {mlInsights[driver.name].overall_assessment.feature_importance_ranking.map((feature, idx) => (
                                <div key={idx} className="ml-feature-item">
                                  <span className="ml-feature-name">{feature.feature.replace('_', ' ')}</span>
                                  <div className="ml-feature-bar">
                                    <div 
                                      className="ml-feature-bar-fill" 
                                      style={{ width: `${(feature.importance || 0) * 100}%` }}
                                    />
                                  </div>
                                  <span className="ml-feature-value">{(feature.importance || 0).toFixed(3)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {mlInsights[driver.name].overall_assessment.key_strengths && 
                         mlInsights[driver.name].overall_assessment.key_strengths.length > 0 && (
                          <div className="ml-strengths">
                            <strong>Strengths:</strong>
                            <ul>
                              {mlInsights[driver.name].overall_assessment.key_strengths.map((strength, idx) => (
                                <li key={idx}>{strength}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {mlInsights[driver.name].overall_assessment.key_weaknesses && 
                         mlInsights[driver.name].overall_assessment.key_weaknesses.length > 0 && (
                          <div className="ml-weaknesses">
                            <strong>Weaknesses:</strong>
                            <ul>
                              {mlInsights[driver.name].overall_assessment.key_weaknesses.map((weakness, idx) => (
                                <li key={idx}>{weakness}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {mlInsights[driver.name].pit_strategy_analysis && (
                      <div className="ml-strategy-analysis">
                        <strong>Pit Strategy Analysis:</strong>
                        <div className="ml-strategy-info">
                          <span>Model Prediction: {mlInsights[driver.name].pit_strategy_analysis.optimal_strategy || 'N/A'}</span>
                          <span>Confidence: {((mlInsights[driver.name].pit_strategy_analysis.optimal_strategy_confidence || 0) * 100).toFixed(1)}%</span>
                          <span>Efficiency Score: {((mlInsights[driver.name].pit_strategy_analysis.strategy_efficiency_score || 0) * 100).toFixed(1)}%</span>
                          {mlInsights[driver.name].pit_strategy_analysis.statistical_significance !== undefined && (
                            <span className="ml-stat-significance">
                              p-value: {(mlInsights[driver.name].pit_strategy_analysis.statistical_significance || 0).toFixed(3)}
                            </span>
                          )}
                        </div>
                        {mlInsights[driver.name].pit_strategy_analysis.confidence_interval && (
                          <div className="ml-confidence-interval-display">
                            Confidence Interval: [{((mlInsights[driver.name].pit_strategy_analysis.confidence_interval[0] || 0) * 100).toFixed(1)}%, 
                            {((mlInsights[driver.name].pit_strategy_analysis.confidence_interval[1] || 0) * 100).toFixed(1)}%]
                          </div>
                        )}
                        {mlInsights[driver.name].pit_strategy_analysis.feature_importance && (
                          <div className="ml-feature-importance-inline">
                            <strong>Feature Importance:</strong>
                            <div className="ml-feature-tags">
                              {Object.entries(mlInsights[driver.name].pit_strategy_analysis.feature_importance).map(([key, value]) => (
                                <span key={key} className="ml-feature-tag">
                                  {key.replace('_', ' ')}: {(value || 0).toFixed(2)}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {mlInsights[driver.name].pit_strategy_analysis.missed_opportunities && 
                         mlInsights[driver.name].pit_strategy_analysis.missed_opportunities.length > 0 && (
                          <div className="ml-missed-opportunities">
                            <strong>Pattern-Detected Missed Opportunities:</strong>
                            <ul>
                              {mlInsights[driver.name].pit_strategy_analysis.missed_opportunities.map((opp, idx) => (
                                <li key={idx}>
                                  <span className="ml-opp-lap">Lap {opp.lap}</span>
                                  <span className="ml-opp-type">[{opp.opportunity_type}]</span>
                                  <span className="ml-opp-desc">{opp.description}</span>
                                  {opp.predicted_time_gain && (
                                    <span className="ml-opp-gain">Predicted Gain: {opp.predicted_time_gain.toFixed(2)}s</span>
                                  )}
                                  {opp.detection_confidence !== undefined && (
                                    <span className="ml-opp-confidence">Confidence: {((opp.detection_confidence || 0) * 100).toFixed(1)}%</span>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {mlInsights[driver.name].tire_management && (
                      <div className="ml-tire-management">
                        <strong>Tire Management Analysis:</strong>
                        <div className="ml-tire-info">
                          <span>Usage Score: {((mlInsights[driver.name].tire_management.tire_usage_score || 0) * 100).toFixed(1)}%</span>
                          {mlInsights[driver.name].tire_management.confidence_interval && (
                            <span className="ml-confidence-interval">
                              CI: [{((mlInsights[driver.name].tire_management.confidence_interval[0] || 0) * 100).toFixed(1)}%, 
                              {((mlInsights[driver.name].tire_management.confidence_interval[1] || 0) * 100).toFixed(1)}%]
                            </span>
                          )}
                          {mlInsights[driver.name].tire_management.optimal_compound_analysis && (
                            <>
                              <span>Model Prediction: {mlInsights[driver.name].tire_management.optimal_compound_analysis.recommended_starting_compound || 'N/A'}</span>
                              {mlInsights[driver.name].tire_management.optimal_compound_analysis.prediction_confidence !== undefined && (
                                <span>Confidence: {((mlInsights[driver.name].tire_management.optimal_compound_analysis.prediction_confidence || 0) * 100).toFixed(1)}%</span>
                              )}
                            </>
                          )}
                        </div>
                        {mlInsights[driver.name].tire_management.tire_wear_analysis?.degradation_correlation !== undefined && (
                          <div className="ml-degradation-correlation">
                            Degradation Correlation: {(mlInsights[driver.name].tire_management.tire_wear_analysis.degradation_correlation || 0).toFixed(3)}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {mlInsights[driver.name].overall_assessment && 
                     mlInsights[driver.name].overall_assessment.top_3_recommendations && 
                     mlInsights[driver.name].overall_assessment.top_3_recommendations.length > 0 && (
                      <div className="ml-top-recommendations">
                        <strong>Model-Predicted Optimizations:</strong>
                        <ul>
                          {mlInsights[driver.name].overall_assessment.top_3_recommendations.map((rec, idx) => (
                            <li key={idx}>
                              <div className="ml-rec-header">
                                <strong>#{rec.priority}</strong>
                                <span className="ml-rec-category">[{rec.category}]</span>
                                {rec.prediction_confidence !== undefined && (
                                  <span className="ml-rec-confidence">Confidence: {((rec.prediction_confidence || 0) * 100).toFixed(1)}%</span>
                                )}
                                {rec.statistical_significance !== undefined && (
                                  <span className="ml-rec-significance">p={rec.statistical_significance.toFixed(3)}</span>
                                )}
                              </div>
                              <div className="ml-rec-content">
                                <span className="ml-rec-text">{rec.recommendation}</span>
                                <span className="ml-rec-benefit">Predicted Benefit: {rec.predicted_benefit || rec.expected_benefit}</span>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {(!driver.insights || driver.insights.length === 0) && 
                 (!driver.recommendations || driver.recommendations.length === 0) &&
                 (!mlInsights[driver.name]) && (
                  <div className="no-insights-message">
                    No significant insights for this driver.
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </motion.section>
      </div>
    </div>
  );
};

export default RaceDashboard;

