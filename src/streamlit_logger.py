
import streamlit as st
from datetime import datetime
import logging
import io

class StreamlitLogger:
    """
    Streamlit UI에 로그를 출력하기 위한 로거 클래스
    session_state를 사용하여 로그 메시지를 저장하고 표시합니다.
    """
    
    def __init__(self):
        if 'log_messages' not in st.session_state:
            st.session_state.log_messages = []
            
    def log(self, message: str, level: str = "INFO"):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        st.session_state.log_messages.append(log_entry)
        
        # 로그가 너무 많이 쌓이면 오래된 것 삭제 (최근 1000줄 유지)
        if len(st.session_state.log_messages) > 1000:
            st.session_state.log_messages.pop(0)
            
    def info(self, message: str):
        self.log(message, "INFO")
        
    def warning(self, message: str):
        self.log(message, "WARNING")
        
    def error(self, message: str):
        self.log(message, "ERROR")
        
    def clear(self):
        """로그 초기화"""
        st.session_state.log_messages = []

    def get_logs(self) -> str:
        """현재까지의 로그를 문자열로 반환"""
        return "\n".join(st.session_state.log_messages)

def get_logger():
    """싱글톤 패턴으로 로거 반환"""
    return StreamlitLogger()
