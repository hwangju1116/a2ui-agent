# /Users/hwangju/.gemini/jetski/scratch/a2ui-agent/tests/test_agent.py
import pytest
import os
from agent import SamsungAgent

def test_agent_initialization():
    # 환경 변수 모킹 또는 설정
    os.environ["PROJECT_ID"] = "test-project"
    os.environ["LOCATION"] = "us-central1"
    
    agent = SamsungAgent("http://localhost:8080")
    
    # 에이전트 기본 정보 검증
    assert agent._agent_name == "samsung_agent"
    assert agent.agent_card.name == "Samsung Agent"
    assert "samsung_comparison" in [skill.id for skill in agent.agent_card.skills]
    print("--- Agent initialization test passed!")

if __name__ == "__main__":
    test_agent_initialization()