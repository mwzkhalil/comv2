-- Initialize DeliveryAudio table for Docker deployment
USE IndoorCricket;

-- Create DeliveryAudio table
CREATE TABLE IF NOT EXISTS DeliveryAudio (
    audio_id INT AUTO_INCREMENT PRIMARY KEY,
    
    delivery_id VARCHAR(50) NOT NULL COMMENT 'References Deliveries.d_id',
    event_id INT UNIQUE COMMENT 'Sequential event identifier',
    match_id VARCHAR(100) NOT NULL,
    
    sentence TEXT NOT NULL COMMENT 'Pre-generated commentary text',
    intensity VARCHAR(20) DEFAULT 'normal' COMMENT 'low/normal/medium/high/extreme',
    excitement_level INT COMMENT '0-10 excitement scale',
    
    audio_file_path VARCHAR(500) COMMENT 'Path to saved TTS audio file',
    audio_generated_at DATETIME COMMENT 'When audio was generated',
    audio_duration_seconds DECIMAL(5,2) COMMENT 'Audio duration in seconds',
    audio_format VARCHAR(20) DEFAULT 'mp3' COMMENT 'Audio file format',
    
    status VARCHAR(50) DEFAULT 'pending' COMMENT 'pending/generated/played/failed',
    play_count INT DEFAULT 0 COMMENT 'How many times played',
    last_played_at DATETIME COMMENT 'Last playback timestamp',
    error_message TEXT COMMENT 'Any generation/playback errors',
    
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_delivery_id (delivery_id),
    INDEX idx_event_id (event_id),
    INDEX idx_match_id (match_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Create CommentaryLog table
CREATE TABLE IF NOT EXISTS CommentaryLog (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    match_id VARCHAR(100),
    event_id INT,
    
    commentary_type VARCHAR(50) COMMENT 'delivery/welcome/break/end',
    commentary_text TEXT NOT NULL,
    intensity VARCHAR(20),
    excitement_level INT COMMENT '0-10 scale',
    
    audio_file_path VARCHAR(500),
    audio_generated_at DATETIME,
    audio_played_at DATETIME,
    audio_duration_seconds DECIMAL(5,2),
    
    status VARCHAR(50) DEFAULT 'pending' COMMENT 'pending/played/failed',
    error_message TEXT,
    
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_match_id (match_id),
    INDEX idx_commentary_type (commentary_type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SELECT 'Database initialized successfully!' AS Status;
SELECT COUNT(*) AS DeliveryAudio_Records FROM DeliveryAudio;
