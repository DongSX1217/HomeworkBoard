// 游戏状态管理
class ClassroomGame {
    constructor() {
        this.playerId = null;
        this.playerName = null;
        this.gameState = null;
        this.cooldowns = {};
        this.statusInterval = null;
        this.isJoined = false;
        
        this.initializeGame();
    }
    
    // 初始化游戏
    initializeGame() {
        // 获取玩家信息
        this.playerName = this.getCookie('fun_name');
        this.studentId = this.getCookie('fun_student_id');
        
        if (this.playerName && this.studentId) {
            this.playerId = `${this.playerName}_${this.studentId}`;
            this.updatePlayerInfo();
        } else {
            // 如果未登录，重定向到认证页面
            window.location.href = '/902504/auth';
            return;
        }
        
        // 绑定事件监听器
        this.bindEvents();
        
        // 开始状态轮询
        this.startStatusPolling();
        
        // 初始加载游戏状态
        this.fetchGameStatus();
    }
    
    // 从cookie获取值
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }
    
    // 绑定事件监听器
    bindEvents() {
        // 动作按钮
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.currentTarget.dataset.action;
                this.performAction(action);
            });
        });
        
        // 控制按钮
        document.getElementById('join-game').addEventListener('click', () => this.joinGame());
        document.getElementById('reset-game').addEventListener('click', () => this.resetGame());
        document.getElementById('leave-game').addEventListener('click', () => this.leaveGame());
        
        // 模态框关闭按钮
        document.getElementById('close-result').addEventListener('click', () => {
            document.getElementById('game-result-modal').style.display = 'none';
        });
        
        // 课桌点击事件
        document.querySelectorAll('.desk').forEach(desk => {
            desk.addEventListener('click', (e) => {
                const action = e.currentTarget.dataset.action;
                this.performAction(action);
            });
        });
    }
    
    // 开始状态轮询
    startStatusPolling() {
        this.statusInterval = setInterval(() => {
            this.fetchGameStatus();
        }, 2000); // 每2秒更新一次状态
    }
    
    // 获取游戏状态
    async fetchGameStatus() {
        try {
            const response = await fetch('/902504/classroom-game/status');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            this.gameState = data;
            this.updateUI();
        } catch (error) {
            console.error('获取游戏状态失败:', error);
            this.addLog('获取游戏状态失败，请检查网络连接', 'danger');
        }
    }
    
    // 加入游戏
    async joinGame() {
        try {
            const response = await fetch('/902504/classroom-game/join', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.isJoined = true;
                this.addLog('已成功加入游戏', 'info');
                this.fetchGameStatus();
            } else {
                this.addLog(`加入游戏失败: ${data.message}`, 'danger');
            }
        } catch (error) {
            console.error('加入游戏失败:', error);
            this.addLog('加入游戏失败，请重试', 'danger');
        }
    }
    
    // 执行动作
    async performAction(action) {
        if (!this.isJoined) {
            this.addLog('请先加入游戏', 'warning');
            return;
        }
        
        // 检查冷却
        if (this.cooldowns[action] && this.cooldowns[action] > Date.now()) {
            const remaining = Math.ceil((this.cooldowns[action] - Date.now()) / 1000);
            this.addLog(`动作冷却中，还剩${remaining}秒`, 'warning');
            return;
        }
        
        try {
            const response = await fetch('/902504/classroom-game/action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ action })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.addLog(data.message, 'success');
                
                // 设置冷却时间
                if (data.cooldown) {
                    this.cooldowns[action] = Date.now() + data.cooldown * 1000;
                    this.updateCooldownDisplay(action, data.cooldown);
                }
                
                // 更新分数
                if (data.score !== undefined) {
                    document.getElementById('current-player-score').textContent = data.score;
                }
            } else {
                if (data.caught) {
                    this.addLog(data.message, 'danger');
                    this.showGameResult(data.message);
                } else {
                    this.addLog(data.message, 'warning');
                }
            }
            
            // 刷新游戏状态
            this.fetchGameStatus();
        } catch (error) {
            console.error('执行动作失败:', error);
            this.addLog('执行动作失败，请重试', 'danger');
        }
    }
    
    // 重置游戏
    async resetGame() {
        try {
            const response = await fetch('/902504/classroom-game/reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.addLog('游戏已重置', 'info');
                this.cooldowns = {};
                this.fetchGameStatus();
            } else {
                this.addLog(`重置游戏失败: ${data.message}`, 'danger');
            }
        } catch (error) {
            console.error('重置游戏失败:', error);
            this.addLog('重置游戏失败，请重试', 'danger');
        }
    }
    
    // 离开游戏
    async leaveGame() {
        try {
            const response = await fetch('/902504/classroom-game/leave', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.isJoined = false;
                this.addLog('已离开游戏', 'info');
                this.fetchGameStatus();
            } else {
                this.addLog(`离开游戏失败: ${data.message}`, 'danger');
            }
        } catch (error) {
            console.error('离开游戏失败:', error);
            this.addLog('离开游戏失败，请重试', 'danger');
        }
    }
    
    // 更新UI
    updateUI() {
        if (!this.gameState) return;
        
        // 更新游戏状态
        document.getElementById('round-counter').textContent = this.gameState.current_round || 0;
        document.getElementById('player-count').textContent = this.gameState.players ? this.gameState.players.length : 0;
        document.getElementById('game-state').textContent = this.gameState.game_active ? '进行中' : '已结束';
        
        // 更新老师状态
        const teacher = document.getElementById('teacher');
        const teacherStatus = document.getElementById('teacher-status');
        const teacherEyes = document.getElementById('teacher-eyes');
        
        if (this.gameState.teacher_looking) {
            teacher.classList.add('teacher-looking');
            teacherEyes.classList.add('teacher-looking');
            teacherStatus.textContent = '老师正在回头看！';
            teacherStatus.style.color = '#e74c3c';
            teacherStatus.style.fontWeight = 'bold';
        } else {
            teacher.classList.remove('teacher-looking');
            teacherEyes.classList.remove('teacher-looking');
            teacherStatus.textContent = '老师正在讲课...';
            teacherStatus.style.color = '#2d3436';
            teacherStatus.style.fontWeight = 'normal';
        }
        
        // 更新玩家列表
        this.updatePlayersList();
        
        // 更新动作按钮状态
        this.updateActionButtons();
        
        // 如果游戏结束，显示结果
        if (!this.gameState.game_active && this.gameState.caught_player) {
            const message = `${this.gameState.caught_player.name}在${this.gameState.caught_player.action}时被老师发现了！`;
            this.showGameResult(message);
        }
    }
    
    // 更新玩家列表
    updatePlayersList() {
        const playersList = document.getElementById('players-list');
        playersList.innerHTML = '';
        
        if (!this.gameState.players || this.gameState.players.length === 0) {
            playersList.innerHTML = '<div class="player-item">暂无玩家</div>';
            return;
        }
        
        this.gameState.players.forEach(player => {
            const playerItem = document.createElement('div');
            playerItem.className = 'player-item';
            
            const playerClass = player.alive ? 'player-alive' : 'player-caught';
            
            playerItem.innerHTML = `
                <span class="player-name ${playerClass}">${player.name}</span>
                <span class="player-score">${player.score}分</span>
            `;
            
            playersList.appendChild(playerItem);
        });
    }
    
    // 更新动作按钮状态
    updateActionButtons() {
        // 更新冷却显示
        Object.keys(this.cooldowns).forEach(action => {
            const remaining = Math.ceil((this.cooldowns[action] - Date.now()) / 1000);
            if (remaining > 0) {
                this.updateCooldownDisplay(action, remaining);
            } else {
                this.updateCooldownDisplay(action, 0);
                delete this.cooldowns[action];
            }
        });
        
        // 根据游戏状态禁用按钮
        const buttons = document.querySelectorAll('.action-btn');
        buttons.forEach(btn => {
            if (!this.gameState.game_active || !this.isJoined) {
                btn.disabled = true;
            } else {
                btn.disabled = false;
            }
        });
    }
    
    // 更新冷却显示
    updateCooldownDisplay(action, seconds) {
        const cooldownElement = document.getElementById(`cooldown-${action.replace('_', '-')}`);
        if (cooldownElement) {
            if (seconds > 0) {
                cooldownElement.textContent = `${seconds}s`;
                cooldownElement.style.display = 'block';
                
                // 禁用按钮
                const button = document.getElementById(`btn-${action.replace('_', '-')}`);
                if (button) {
                    button.disabled = true;
                }
            } else {
                cooldownElement.textContent = '';
                cooldownElement.style.display = 'none';
                
                // 启用按钮
                const button = document.getElementById(`btn-${action.replace('_', '-')}`);
                if (button && this.gameState.game_active && this.isJoined) {
                    button.disabled = false;
                }
            }
        }
    }
    
    // 更新玩家信息显示
    updatePlayerInfo() {
        document.getElementById('current-player-name').textContent = this.playerName;
    }
    
    // 添加日志
    addLog(message, type = 'info') {
        const logContainer = document.getElementById('game-log');
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        logEntry.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
        
        logContainer.appendChild(logEntry);
        
        // 自动滚动到底部
        logContainer.scrollTop = logContainer.scrollHeight;
        
        // 限制日志数量
        const logs = logContainer.querySelectorAll('.log-entry');
        if (logs.length > 50) {
            logs[0].remove();
        }
    }
    
    // 显示游戏结果
    showGameResult(message) {
        const modal = document.getElementById('game-result-modal');
        const title = document.getElementById('result-title');
        const messageElement = document.getElementById('result-message');
        
        title.textContent = '游戏结束';
        messageElement.textContent = message;
        
        modal.style.display = 'flex';
    }
}

// 页面加载完成后初始化游戏
document.addEventListener('DOMContentLoaded', () => {
    window.classroomGame = new ClassroomGame();
});