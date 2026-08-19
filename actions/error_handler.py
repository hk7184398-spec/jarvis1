"""
JARVIS Error Handler
Centralized error handling, logging, and recovery strategies
"""

import traceback
import logging
from typing import Optional, Callable, Any
from datetime import datetime
from pathlib import Path


class JARVISErrorHandler:
    """Central error handler for JARVIS with logging and recovery."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.logger = self._setup_logger()
        self.error_count = 0
        self.recovery_callbacks: dict[str, Callable] = {}
    
    def _setup_logger(self) -> logging.Logger:
        """Configure logging to file and console."""
        logger = logging.getLogger("JARVIS")
        logger.setLevel(logging.DEBUG)
        
        # File handler
        log_file = self.log_dir / f"jarvis_{datetime.now().strftime('%Y%m%d')}.log"
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def handle_exception(
        self,
        exception: Exception,
        context: str = "",
        recovery_strategy: Optional[Callable] = None
    ) -> bool:
        """
        Handle an exception with optional recovery.
        
        Args:
            exception: The exception to handle
            context: Context about where the error occurred
            recovery_strategy: Optional callback to attempt recovery
        
        Returns:
            True if recovery succeeded, False otherwise
        """
        self.error_count += 1
        
        # Log the error
        self.logger.error(
            f"Error in {context}: {str(exception)}\n{traceback.format_exc()}"
        )
        
        # Attempt recovery
        if recovery_strategy:
            try:
                recovery_strategy()
                self.logger.info(f"Recovery successful for: {context}")
                return True
            except Exception as e:
                self.logger.error(f"Recovery failed: {str(e)}")
                return False
        
        return False
    
    def register_recovery(self, error_type: str, callback: Callable) -> None:
        """Register a recovery callback for a specific error type."""
        self.recovery_callbacks[error_type] = callback
    
    def log_info(self, message: str) -> None:
        """Log info level message."""
        self.logger.info(message)
    
    def log_warning(self, message: str) -> None:
        """Log warning level message."""
        self.logger.warning(message)
    
    def log_debug(self, message: str) -> None:
        """Log debug level message."""
        self.logger.debug(message)


# Global error handler instance
_error_handler = None


def get_error_handler() -> JARVISErrorHandler:
    """Get or create the global error handler."""
    global _error_handler
    if _error_handler is None:
        _error_handler = JARVISErrorHandler()
    return _error_handler
