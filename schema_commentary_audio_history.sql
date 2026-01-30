-- Table to store commentary audio history for each ball
CREATE TABLE IF NOT EXISTS CommentaryAudioHistory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ball_id VARCHAR(50) NOT NULL,
    match_id VARCHAR(50) NOT NULL,
    audio_path VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_seconds FLOAT,
    FOREIGN KEY (ball_id) REFERENCES Deliveries(ball_id),
    FOREIGN KEY (match_id) REFERENCES MatchSlot(slot_id)
);
