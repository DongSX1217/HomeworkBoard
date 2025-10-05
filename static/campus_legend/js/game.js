// 校园传说游戏前端逻辑
class CampusLegendGame {
    constructor() {
        this.socket = null;
        this.playerId = null;
        this.gameState = null;
        this.isJoined = false;
        
        this.initializeElements();
        this.setupEventListeners();
        this.connectToServer();
    }
    
    // 初始化DOM元素引用
    initializeElements() {
        // 游戏状态元素
        this.elements = {
            playerName: document.getElementById('player-name'),
            playerId: document.getElementById('player-id'),
            onlineCount: document.getElementById('online-count'),
            solvedCount: document.getElementById('solved-count'),
            
            // 位置信息
            locationName: document.getElementById('location-name'),
            locationDescription: document.getElementById('location-description'),
            
            // 事件区域
            eventSection: document.getElementById('event-section'),
            eventDescription: document.getElementById('event-description'),
            choicesContainer: document.getElementById('choices-container'),
            
            // 合作事件
            cooperationSection: document.getElementById('cooperation-section'),
            cooperationMessage: document.getElementById('cooperation-message'),
            participantsList: document.getElementById('participants-list'),
            
            // 移动控制
            locationsContainer: document.getElementById('locations-container'),
            
            // 玩家列表
            playersList: document.getElementById('players-list'),
            
            // 聊天区域
            chatMessages: document.getElementById('chat-messages'),
            chatInput: document.getElementById('chat-input'),
            sendChat: document.getElementById('send-chat'),
            
            // 游戏控制
            joinGame: document.getElementById('join-game'),
            leaveGame: document.getElementById('leave-game'),
            resetGame: document.getElementById('reset-game'),
            
            // 消息提示
            messageToast: document.getElementById('message-toast')
        };
    }
    
    // 设置事件监听器
    setupEventListeners() {
        // 游戏控制按钮
        this.elements.joinGame.addEventListener('click', () => this.joinGame());
        this.elements.leaveGame.addEventListener('click', () => this.leaveGame());
        this.elements.resetGame.addEventListener('click', () => this.resetGame());
        
        // 聊天功能
        this.elements.sendChat.addEventListener('click', () => this.sendChatMessage());
        this.elements.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendChatMessage();
            }
        });
        
        // 定期更新游戏状态
        setInterval(() => this.updateGameStatus(), 3000);
    }
    
    // 连接到服务器
    connectToServer() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            this.showMessage('已连接到服务器', 'success');
        });
        
        this.socket.on('disconnect', () => {
            this.showMessage('与服务器断开连接', 'error');
        });
        
        // 监听游戏状态更新
        this.socket.on('game_state_update', (data) => {
            this.handleGameStateUpdate(data);
        });
        
        // 监听聊天消息
        this.socket.on('chat_message', (data) => {
            this.displayChatMessage(data);
        });
        
        // 监听系统消息
        this.socket.on('system_message', (data) => {
            this.displaySystemMessage(data);
        });
    }
    
    // 加入游戏
    async joinGame() {
        try {
            const response = await fetch('/902504/game/campus_legend/join', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.isJoined = true;
                this.elements.joinGame.classList.add('hidden');
                this.elements.leaveGame.classList.remove('hidden');
                this.showMessage('成功加入游戏', 'success');
                
                // 初始化玩家ID
                const name = this.elements.playerName.textContent;
                const studentId = this.elements.playerId.textContent;
                this.playerId = `${name}_${studentId}`;
                
                // 更新游戏状态
                this.updateGameStatus();
            } else {
                this.showMessage(result.message, 'error');
            }
        } catch (error) {
            this.showMessage('加入游戏失败: ' + error.message, 'error');
        }
    }
    
    // 离开游戏
    async leaveGame() {
        try {
            const response = await fetch('/902504/game/campus_legend/leave', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.isJoined = false;
                this.elements.joinGame.classList.remove('hidden');
                this.elements.leaveGame.classList.add('hidden');
                this.showMessage('已离开游戏', 'info');
            } else {
                this.showMessage(result.message, 'error');
            }
        } catch (error) {
            this.showMessage('离开游戏失败: ' + error.message, 'error');
        }
    }
    
    // 重置游戏
    async resetGame() {
        if (!confirm('确定要重置游戏吗？所有进度将被清除。')) {
            return;
        }
        
        try {
            const response = await fetch('/902504/game/campus_legend/reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showMessage('游戏已重置', 'success');
                this.updateGameStatus();
            } else {
                this.showMessage(result.message, 'error');
            }
        } catch (error) {
            this.showMessage('重置游戏失败: ' + error.message, 'error');
        }
    }
    
    // 移动玩家
    async moveToLocation(locationId) {
        try {
            const response = await fetch('/902504/game/campus_legend/move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ location: locationId })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showMessage(result.message, 'success');
                this.updateGameStatus();
            } else {
                this.showMessage(result.message, 'error');
            }
        } catch (error) {
            this.showMessage('移动失败: ' + error.message, 'error');
        }
    }
    
    // 执行选择
    async makeChoice(choiceId) {
        try {
            const response = await fetch('/902504/game/campus_legend/action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ choice: choiceId })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showMessage(result.message, 'success');
                
                // 如果是合作事件且未完成，显示合作信息
                if (result.cooperation_success === false) {
                    this.displayCooperationEvent(result);
                } else {
                    this.elements.cooperationSection.classList.add('hidden');
                }
                
                this.updateGameStatus();
            } else {
                this.showMessage(result.message, 'error');
            }
        } catch (error) {
            this.showMessage('执行选择失败: ' + error.message, 'error');
        }
    }
    
    // 更新游戏状态
    async updateGameStatus() {
        if (!this.isJoined) return;
        
        try {
            const response = await fetch('/902504/game/campus_legend/status');
            const gameState = await response.json();
            
            if (!gameState.error) {
                this.gameState = gameState;
                this.updateUI();
            }
        } catch (error) {
            console.error('获取游戏状态失败:', error);
        }
    }
    
    // 更新UI
    updateUI() {
        if (!this.gameState) return;
        
        // 更新基本信息
        this.elements.onlineCount.textContent = this.gameState.total_players;
        this.elements.solvedCount.textContent = this.gameState.solved_puzzles_count;
        
        // 更新位置信息
        this.elements.locationName.textContent = this.gameState.location_name;
        this.elements.locationDescription.textContent = this.gameState.location_description;
        
        // 更新事件信息
        if (this.gameState.current_event) {
            this.elements.eventSection.classList.remove('hidden');
            this.elements.eventDescription.textContent = this.gameState.current_event.description;
            this.renderChoices(this.gameState.current_event.choices);
        } else {
            this.elements.eventSection.classList.add('hidden');
        }
        
        // 更新合作事件信息
        if (Object.keys(this.gameState.cooperation_events).length > 0) {
            this.elements.cooperationSection.classList.remove('hidden');
            this.renderCooperationEvents(this.gameState.cooperation_events);
        } else {
            this.elements.cooperationSection.classList.add('hidden');
        }
        
        // 更新移动控制
        this.renderLocations();
        
        // 更新玩家列表
        this.renderPlayersList();
    }
    
    // 渲染选择按钮
    renderChoices(choices) {
        this.elements.choicesContainer.innerHTML = '';
        
        choices.forEach(choice => {
            const button = document.createElement('button');
            button.className = 'choice-btn';
            button.textContent = choice.text;
            button.addEventListener('click', () => this.makeChoice(choice.id));
            this.elements.choicesContainer.appendChild(button);
        });
    }
    
    // 渲染地点按钮
    renderLocations() {
        this.elements.locationsContainer.innerHTML = '';
        
        // 这里应该从服务器获取可用位置，暂时使用硬编码
        const locations = [
            { id: 'dorm_hallway', name: '宿舍走廊' },
            { id: 'classroom', name: '教室' },
            { id: 'library', name: '图书馆' },
            { id: 'playground', name: '操场' },
            { id: 'toilet', name: '厕所' }
        ];
        
        locations.forEach(location => {
            const button = document.createElement('button');
            button.className = 'location-btn';
            button.textContent = location.name;
            button.disabled = this.gameState.current_location === location.id;
            button.addEventListener('click', () => this.moveToLocation(location.id));
            this.elements.locationsContainer.appendChild(button);
        });
    }
    
    // 渲染玩家列表
    renderPlayersList() {
        this.elements.playersList.innerHTML = '';
        
        if (this.gameState.players.length === 0) {
            this.elements.playersList.innerHTML = '<div class="player-item">暂无其他玩家</div>';
            return;
        }
        
        this.gameState.players.forEach(player => {
            const playerElement = document.createElement('div');
            playerElement.className = 'player-item';
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'player-name';
            nameSpan.textContent = player.name;
            
            const locationSpan = document.createElement('span');
            locationSpan.className = 'player-location';
            locationSpan.textContent = player.location_name;
            
            playerElement.appendChild(nameSpan);
            playerElement.appendChild(locationSpan);
            
            // 高亮当前玩家
            if (player.is_current_player) {
                playerElement.style.backgroundColor = '#2a3a2a';
                playerElement.style.padding = '5px';
                playerElement.style.borderRadius = '3px';
            }
            
            this.elements.playersList.appendChild(playerElement);
        });
    }
    
    // 渲染合作事件
    renderCooperationEvents(events) {
        // 目前只显示第一个合作事件
        const eventKey = Object.keys(events)[0];
        const event = events[eventKey];
        
        this.elements.cooperationMessage.textContent = 
            `需要 ${event.required_players} 名玩家合作完成。当前参与: ${event.participants.length}/${event.required_players}`;
        
        // 显示参与者
        const participantNames = event.participants.map(pid => {
            const player = this.gameState.players.find(p => p.id === pid);
            return player ? player.name : '未知玩家';
        });
        
        this.elements.participantsList.textContent = 
            `参与者: ${participantNames.join(', ') || '暂无'}`;
    }
    
    // 显示合作事件信息
    displayCooperationEvent(result) {
        this.elements.cooperationSection.classList.remove('hidden');
        this.elements.cooperationMessage.textContent = result.message;
        
        if (result.participants) {
            const participantNames = result.participants.map(pid => {
                const player = this.gameState.players.find(p => p.id === pid);
                return player ? player.name : '未知玩家';
            });
            
            this.elements.participantsList.textContent = 
                `参与者: ${participantNames.join(', ')}`;
        }
    }
    
    // 发送聊天消息
    sendChatMessage() {
        const message = this.elements.chatInput.value.trim();
        
        if (!message) return;
        
        // 发送到服务器
        if (this.socket) {
            this.socket.emit('chat_message', {
                player: this.elements.playerName.textContent,
                message: message
            });
        }
        
        this.elements.chatInput.value = '';
    }
    
    // 显示聊天消息
    displayChatMessage(data) {
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message player';
        
        const timestamp = new Date().toLocaleTimeString();
        
        messageElement.innerHTML = `
            <span class="sender">${data.player}:</span>
            <span>${data.message}</span>
            <span class="timestamp">${timestamp}</span>
        `;
        
        this.elements.chatMessages.appendChild(messageElement);
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }
    
    // 显示系统消息
    displaySystemMessage(data) {
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message system';
        
        const timestamp = new Date().toLocaleTimeString();
        
        messageElement.innerHTML = `
            <span>${data.message}</span>
            <span class="timestamp">${timestamp}</span>
        `;
        
        this.elements.chatMessages.appendChild(messageElement);
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }
    
    // 显示消息提示
    showMessage(message, type = 'info') {
        const toast = this.elements.messageToast;
        toast.textContent = message;
        toast.className = '';
        toast.classList.add(type);
        toast.classList.remove('hidden');
        
        // 3秒后自动隐藏
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    }
    
    // 处理游戏状态更新
    handleGameStateUpdate(data) {
        this.gameState = data;
        this.updateUI();
    }
}

// 页面加载完成后初始化游戏
document.addEventListener('DOMContentLoaded', () => {
    window.campusLegendGame = new CampusLegendGame();
});