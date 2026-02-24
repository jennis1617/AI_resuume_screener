"""
Resume Quality Analysis Module
"""

import json
from utils.groq_client import create_groq_completion
import streamlit as st


class ResumeAnalyzer:
    def __init__(self, client):
        self.client = client
        self.fallback_client = st.session_state.get('fallback_client')

    def analyze_resume(self, resume_text, mask_pii_enabled=False):
        """Analyze resume for quality checks and potential issues."""
        
        # Note: We don't mask here as the text is already processed during parsing
        prompt = f"""
        Review the following resume for quality and completeness.
       
        EVALUATION CHECKLIST:
        1. PREVIOUS EMPLOYMENT: Did the candidate previously work at "NexTurn"?
        2. EMPLOYMENT GAPS: Identify any gaps in employment history exceeding 6 months. Provide approximate dates.
        3. EXPERIENCE CONSISTENCY: Check if years of experience with specific technologies seem realistic (e.g., 10 years in a technology only 3 years old).
        4. OVERLAPPING DATES: Identify any overlapping employment dates or suspicious claims.
        5. EXPERTISE AREAS: List the candidate's primary areas of expertise and domain knowledge.
 
        Resume Text:
        {resume_text[:8000]}
 
        Return ONLY a valid JSON object with this structure:
        {{
            "is_previous_employee": false,
            "nexturn_history_details": "None or description if previously employed",
            "career_gaps": ["gap description 1", "gap description 2"],
            "technical_anomalies": ["anomaly description 1"],
            "fake_indicators": ["concern description 1"],
            "domain_knowledge": ["expertise area 1", "expertise area 2"],
            "summary": "brief overall assessment"
        }}
        
        Use empty arrays for any category with no findings.
        """
        
        try:
            response = create_groq_completion(
                self.client,
                self.fallback_client,
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an expert resume reviewer. Return only valid JSON with the exact structure requested."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                return json.loads(content[json_start:json_end])
            else:
                return self._empty_result()
                
        except Exception as e:
            print(f"Analysis error: {str(e)}")
            return self._empty_result()
    
    def _empty_result(self):
        """Return empty result structure."""
        return {
            "is_previous_employee": False,
            "nexturn_history_details": "None",
            "career_gaps": [],
            "technical_anomalies": [],
            "fake_indicators": [],
            "domain_knowledge": [],
            "summary": "Analysis could not be completed"
        }