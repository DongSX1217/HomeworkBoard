let refreshInterval;
let intervalId;
let isFullscreen = false;
let globalLabels = []; // 全局标签缓存

// 窗口大小变化时重新布局
let resizeTimeout;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        fetchHomeworkAndLabels();
    }, 250);
});

// 监听全屏变化事件
document.addEventListener('fullscreenchange', handleFullscreenChange);
document.addEventListener('webkitfullscreenchange', handleFullscreenChange); // Safari
document.addEventListener('msfullscreenchange', handleFullscreenChange); // IE/Edge

// 页面加载完成后初始化
window.onload = function() {
    loadSettings();
    startAutoRefresh();
    applyHideExpired();
    loadQuickPublishData();
    updateFloatButtonPosition();
    initSubjectSelects(); // 初始化学科选择框
    initSubjectChangeListeners(); // 初始化学科变更监听
    
    // 添加全局点击事件处理，确保选择框可以正常工作
    document.addEventListener('click', function(e) {
        // 如果点击的是选择框，不阻止默认行为
        if (e.target.classList.contains('subject-select')) {
            return;
        }
    });

    // 添加窗口大小变化监听
    window.addEventListener('resize', handleWindowResize);
};

// 加载设置（从cookie）
function loadSettings() {
    const savedInterval = getCookie("refreshInterval");
    if (savedInterval) {
        refreshInterval = parseInt(savedInterval);
        document.getElementById("refreshInterval").value = refreshInterval;
    } else {
        refreshInterval = 600;
    }
    const savedFontSize = getCookie("fontSize");
    if (savedFontSize) {
        document.body.style.fontSize = savedFontSize + 'px';
        document.getElementById("fontSize").value = savedFontSize;
    } else {
        // 设置默认字体大小为20px
        document.getElementById("fontSize").value = 20;
    }
    const hideExpired = getCookie("hideExpired");
    if (hideExpired === "true") {
        document.getElementById("hideExpired").checked = true;
        applyHideExpired();
    }
    const EditButton = getCookie("EditButton");
    if (EditButton === "true") {
        document.getElementById("EditButton").checked = true;
    }
    const DeleteButton = getCookie("DeleteButton");
    if (DeleteButton === "true") {
        document.getElementById("DeleteButton").checked = true;
    }
    const quickPublishButton = getCookie("quickPublishButton");
    if (quickPublishButton === "true") {
        document.getElementById("quickPublishButton").checked = true;
        quickPublishEnabled = true;
        showQuickPublishButton();
    }
}

// 保存设置（到cookie）
function saveSettings() {
    const newInterval = document.getElementById("refreshInterval").value;
    if (newInterval >= 20 && newInterval <= 3600) {
        refreshInterval = parseInt(newInterval);
        setCookie("refreshInterval", refreshInterval, 30);
        if (intervalId) clearInterval(intervalId);
        startAutoRefresh();
    } else {
        alert('刷新间隔必须在20~3600秒之间');
        return;
    }
    const fontSize = document.getElementById("fontSize").value;
    if (fontSize >= 5 && fontSize <= 50) {
        document.body.style.fontSize = fontSize + 'px';
        setCookie("fontSize", fontSize, 30);
    } else {
        alert('字体大小必须在5~50像素之间');
        return;
    }
    const hideExpired = document.getElementById("hideExpired").checked;
    setCookie("hideExpired", hideExpired, 30);
    const EditButton = document.getElementById("EditButton").checked;
    setCookie("EditButton", EditButton, 30);
    const DeleteButton = document.getElementById("DeleteButton").checked;
    setCookie("DeleteButton", DeleteButton, 30);
    const quickPublishButton = document.getElementById("quickPublishButton").checked;
    setCookie("quickPublishButton", quickPublishButton, 30);
    
    if (quickPublishButton) {
        quickPublishEnabled = true;
        showQuickPublishButton();
    } else {
        quickPublishEnabled = false;
        hideQuickPublishButton();
    }

    applyHideExpired();
    closeSettings();
    alert('设置已保存');
}

function setCookie(name, value, days) {
    const expires = new Date();
    expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = name + '=' + value + ';expires=' + expires.toUTCString() + ';path=/';
}

function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for(let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) == ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

// 调整字体大小
function adjustFontSize(change) {
    const fontSizeInput = document.getElementById("fontSize");
    let currentSize = parseInt(fontSizeInput.value) || 20;
    currentSize += change;
    
    // 限制字体大小在合理范围内
    if (currentSize < 5) currentSize = 5;
    if (currentSize > 50) currentSize = 50;
    
    fontSizeInput.value = currentSize;
    document.body.style.fontSize = currentSize + 'px';
}

// 开始自动刷新
function startAutoRefresh() {
    fetchHomeworkAndLabels();
    intervalId = setInterval(fetchHomeworkAndLabels, refreshInterval * 1000);
}

// 获取作业和标签数据
function fetchHomeworkAndLabels() {
    // 获取学科排序配置
    const subjectsPromise = fetch('/api/subjects')
        .then(response => {
            if (response.ok) return response.json();
            throw new Error('Subjects file not found');
        })
        .then(subjects => {
            // 从完整对象数组中提取学科名称
            return subjects.map(subject => subject.name);
        })
        .catch(() => null);

    // 获取作业数据
    const homeworkPromise = fetch('/api/homework')
        .then(response => response.json());

    // 并行处理两个请求的结果
    Promise.all([subjectsPromise, homeworkPromise])
        .then(([subjectsOrder, data]) => {
            globalLabels = data.labels || [];
            updateHomeworkContainer(data.submissions, globalLabels, subjectsOrder);
        })
        .catch(error => {
            console.error('获取作业数据失败:', error);
        });
}

// 计算最大列高度（优化版本）
function calculateMaxColumnHeight() {
    const screenHeight = window.innerHeight;
    
    // 获取所有固定元素
    const headerElement = document.querySelector('h1');
    const topButtonsElement = document.querySelector('.top-buttons');
    const homeButtonElement = document.querySelector('.home-button');
    
    // 计算固定元素的总高度
    let totalFixedHeight = 0;
    
    // 标题高度（包括margin）
    if (headerElement) {
        const headerStyle = getComputedStyle(headerElement);
        totalFixedHeight += headerElement.offsetHeight + 
                           parseFloat(headerStyle.marginTop) + 
                           parseFloat(headerStyle.marginBottom);
    }
    
    // 顶部按钮高度
    if (topButtonsElement) {
        const topButtonsStyle = getComputedStyle(topButtonsElement);
        totalFixedHeight += topButtonsElement.offsetHeight + 
                           parseFloat(topButtonsStyle.marginTop) + 
                           parseFloat(topButtonsStyle.marginBottom);
    }
    
    // 主页按钮高度
    if (homeButtonElement) {
        const homeButtonStyle = getComputedStyle(homeButtonElement);
        totalFixedHeight += homeButtonElement.offsetHeight + 
                           parseFloat(homeButtonStyle.marginTop) + 
                           parseFloat(homeButtonStyle.marginBottom);
    }
    
    // 容器边距和安全边距
    const containerMargin = 10; 
    const safetyMargin = 2; 
    
    // 返回可用高度
    return Math.max(200, screenHeight - totalFixedHeight - containerMargin - safetyMargin);
}

// 计算作业项的实际估算高度（优化版本）
function calculateItemHeight(submission) {
    const bodyStyle = getComputedStyle(document.body);
    const currentFontSize = parseFloat(bodyStyle.fontSize);
    const baseFontSize = 16;
    const fontScale = currentFontSize / baseFontSize;
    
    // 基础结构高度
    const baseStructureHeight = Math.ceil(65 * fontScale);
    
    // 内容高度估算（优化行数计算）
    const content = submission.content || '';
    const charsPerLine = Math.max(16, Math.floor(24 / fontScale)); 
    const lineHeight = Math.ceil(15 * fontScale); 
    const contentLines = Math.max(1, Math.ceil(content.length / charsPerLine));
    const contentHeight = Math.ceil(contentLines * lineHeight);
    
    // 标签高度（考虑多行标签）
    const labelCount = (submission.labels && submission.labels.length) || 
                      (submission.label_ids && submission.label_ids.length) || 0;
    const labelLines = Math.ceil(labelCount / 3); 
    const labelHeight = labelCount > 0 ? Math.ceil(labelLines * 20 * fontScale) : 0; 
    
    // 内边距、边框和间距
    const paddingAndBorder = Math.ceil(10 * fontScale); 
    const itemSpacing = Math.ceil(4 * fontScale); 
    
    // 总高度（减少安全边距）
    const totalHeight = baseStructureHeight + contentHeight + labelHeight + 
                        paddingAndBorder + itemSpacing;
    
    return Math.ceil(totalHeight);
}

// 计算学科标题的高度（优化版本）
function calculateSubjectTitleHeight() {
    const bodyStyle = getComputedStyle(document.body);
    const currentFontSize = parseFloat(bodyStyle.fontSize);
    const baseFontSize = 16;
    const fontScale = currentFontSize / baseFontSize;
    
    // 学科标题的基础高度（微调）
    const baseTitleHeight = Math.ceil(30 * fontScale); 
    const titlePadding = Math.ceil(10 * fontScale); 
    const titleMargin = Math.ceil(5 * fontScale); 
    
    return baseTitleHeight + titlePadding + titleMargin;
}

// 顺序填充各列（优化版本）
function fillColumnsSequentially(items, columns, colCount) {
    if (items.length === 0) return;
    
    const maxColumnHeight = calculateMaxColumnHeight();
    const columnHeights = new Array(colCount).fill(0);
    const columnSubjects = new Array(colCount).fill(0).map(() => ({}));
    
    // 按学科分组项目
    const subjectGroups = {};
    items.forEach(item => {
        if (!subjectGroups[item.subject]) {
            subjectGroups[item.subject] = [];
        }
        subjectGroups[item.subject].push(item);
    });
    
    // 按学科顺序处理
    const subjectOrder = Object.keys(subjectGroups);
    
    subjectOrder.forEach(subject => {
        const subjectItems = subjectGroups[subject];
        let subjectStartColumn = -1;
        
        // 为每个学科预先计算学科标题高度
        const subjectTitleHeight = calculateSubjectTitleHeight();
        
        subjectItems.forEach((item, index) => {
            // 如果是学科的第一个项目，需要加上学科标题高度
            const itemTotalHeight = index === 0 ? 
                item.estimatedHeight + subjectTitleHeight : 
                item.estimatedHeight;
                
            let targetColumn = findTargetColumn(columnHeights, itemTotalHeight, maxColumnHeight, subjectStartColumn);
            
            // 如果找不到合适的列，使用最后一列（修改这里）
            // 现在findTargetColumn函数已经返回最后一列，所以这里不需要额外处理
            
            // 记录学科开始的列
            if (subjectStartColumn === -1) {
                subjectStartColumn = targetColumn;
            }
            
            // 判断是否是延续
            const isContinuation = (targetColumn > subjectStartColumn);
            
            // 添加作业项并获取实际高度
            const actualHeight = addHomeworkItemToColumnSequentially(
                item, 
                columns[targetColumn], 
                columnSubjects[targetColumn],
                isContinuation,
                index === 0 // 是否是学科的第一个项目
            );
            
            // 使用实际高度更新列高
            columnHeights[targetColumn] += actualHeight;
        });
    });
}

// 找到目标列（优化版本）
function findTargetColumn(columnHeights, itemHeight, maxHeight, subjectStartColumn) {
    // 优先尝试从学科开始的列开始
    if (subjectStartColumn !== -1) {
        for (let i = subjectStartColumn; i < columnHeights.length; i++) {
            // 增加容错空间：允许超出最大高度8%以内
            const tolerance = maxHeight * 0.08;
            if (columnHeights[i] + itemHeight <= maxHeight + tolerance) {
                return i;
            }
        }
    }
    
    // 如果学科开始的列不合适，从头开始找
    for (let i = 0; i < columnHeights.length; i++) {
        const tolerance = maxHeight * 0.05;
        if (columnHeights[i] + itemHeight <= maxHeight + tolerance) {
            return i;
        }
    }
    
    // 如果所有列都放不下，返回最后一列（修改这里）
    return columnHeights.length - 1;
}

// 顺序添加作业项到指定列（返回实际高度）
function addHomeworkItemToColumnSequentially(item, column, columnSubjects, subjectContinuing, isFirstItem) {
    const subject = item.subject;
    const submission = item.submission;
    
    // 检查该列是否已有该学科
    if (!columnSubjects[subject]) {
        // 创建新的学科部分
        const subjectSection = document.createElement('div');
        subjectSection.className = 'subject-section';
        if (subjectContinuing) {
            subjectSection.classList.add('subject-continued');
        }
        
        const subjectTitle = document.createElement('div');
        subjectTitle.className = 'subject-title';
        subjectTitle.textContent = subject + (subjectContinuing ? " (续)" : "");
        subjectSection.appendChild(subjectTitle);
        
        const homeworkList = document.createElement('ul');
        homeworkList.className = 'homework-list';
        subjectSection.appendChild(homeworkList);
        
        column.appendChild(subjectSection);
        columnSubjects[subject] = {
            element: homeworkList,
            section: subjectSection
        };
    }
    
    // 创建作业项
    const homeworkItem = createHomeworkItem(submission);
    columnSubjects[subject].element.appendChild(homeworkItem);
    
    // 如果是第一个项目，测量整个学科部分的高度
    // 如果不是第一个项目，只测量作业项的高度
    if (isFirstItem) {
        // 对于第一个项目，测量整个学科部分以获取准确高度
        return getElementHeight(columnSubjects[subject].section);
    } else {
        // 对于后续项目，只测量作业项的高度
        return getElementHeight(homeworkItem);
    }
}

// 获取元素的实际高度（包括margin）
function getElementHeight(element) {
    // 强制重排以确保测量准确
    const height = element.offsetHeight;
    
    const style = getComputedStyle(element);
    const marginTop = parseFloat(style.marginTop) || 0;
    const marginBottom = parseFloat(style.marginBottom) || 0;
    
    return height + marginTop + marginBottom;
}

// 更新作业容器函数中的列数计算也做相应调整
function getColumnCount() {
    const width = window.innerWidth;
    if (width <= 600) return 1;
    if (width <= 900) return 2;
    if (width <= 1200) return 3;
    return 4;
}

// 更新作业容器（顺序填充各列，允许学科拆分）
function updateHomeworkContainer(submissions, labels, subjectsOrder) {
    const container = document.getElementById('homeworkContainer'); // 作业容器
    container.innerHTML = ''; // 清空现有内容
    
    if (!submissions || Object.keys(submissions).length === 0) { // 无作业信息
        const noSubmissionsDiv = document.createElement('div'); 
        noSubmissionsDiv.className = 'no-submissions';
        noSubmissionsDiv.textContent = '暂无作业信息';
        container.appendChild(noSubmissionsDiv);
        return;
    }

    const colCount = getColumnCount(); // 获取当前列数
    const columns = []; // 列数组
    for (let i = 0; i < colCount; i++) { // 创建列
        const col = document.createElement('div'); // 创建列元素
        col.className = 'column'; // 添加列样式
        columns.push(col); // 添加列
        container.appendChild(col); // 添加到容器
    }

    // 收集所有作业项（按学科和时间排序）
    const allHomeworkItems = []; // 作业项数组
    let subjectOrder; // 科目排序数组
    if (subjectsOrder && Array.isArray(subjectsOrder)) { // 如果有学科排序配置
        subjectOrder = subjectsOrder.filter(subject => submissions.hasOwnProperty(subject)); // 过滤有效学科
    } else {
        subjectOrder = Object.keys(submissions); // 否则使用原始学科
    }
    
    subjectOrder.forEach(subject => {
        // 按时间倒序排列（最新的在前）
        const sortedList = submissions[subject].slice().sort((a, b) => 
            b.timestamp.localeCompare(a.timestamp));
        
        sortedList.forEach(submission => {
            allHomeworkItems.push({
                subject: subject,
                submission: submission,
                estimatedHeight: calculateItemHeight(submission)
            });
        });
    });

    // 顺序填充各列
    fillColumnsSequentially(allHomeworkItems, columns, colCount);
    applyHideExpired(); // 隐藏过期作业
}

// 打开设置弹窗
function openSettings() {
    // 如果当前是全屏模式，先退出全屏
    if (isFullscreen) {
        exitFullscreen();
    }
    document.getElementById("settingsModal").style.display = "block";
}

// 退出全屏的函数
function exitFullscreen() {
    if (document.exitFullscreen) {
        document.exitFullscreen();
    } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
    } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
    }
    
    const container = document.querySelector('.container');
    container.classList.remove('fullscreen');
    document.querySelector('.top-buttons button:nth-child(3)').textContent = '全屏';
    isFullscreen = false;
}

// 关闭设置弹窗
function closeSettings() {
    document.getElementById("settingsModal").style.display = "none";
}

// 切换全屏模式
function toggleFullscreen() {
    const container = document.querySelector('.container');
    
    // 如果模态窗口打开，先关闭
    const settingsModal = document.getElementById("settingsModal");
    const quickPublishModal = document.getElementById("quickPublishModal");
    const quickPublishModal2 = document.getElementById("quickPublishModal2");
    
    if (settingsModal.style.display === "block") {
        closeSettings();
    }
    if (quickPublishModal.style.display === "block") {
        closeQuickPublishModal();
    }
    if (quickPublishModal2.style.display === "block") {
        closeQuickPublishModal2();
    }
    
    if (!document.fullscreenElement) {
        // 进入全屏
        if (container.requestFullscreen) {
            container.requestFullscreen();
        } else if (container.webkitRequestFullscreen) {
            container.webkitRequestFullscreen(); // Safari
        } else if (container.msRequestFullscreen) {
            container.msRequestFullscreen(); // IE/Edge
        }
        
        container.classList.add('fullscreen');
        document.querySelector('.top-buttons button:nth-child(3)').textContent = '退出全屏';
        isFullscreen = true;
        
        // 全屏后重新布局
        setTimeout(() => {
            fetchHomeworkAndLabels();
        }, 300);
    } else {
        // 退出全屏
        exitFullscreen();
        
        // 退出全屏后重新布局
        setTimeout(() => {
            fetchHomeworkAndLabels();
        }, 300);
    }
}

function handleFullscreenChange() {
    const container = document.querySelector('.container');
    const fullscreenButton = document.querySelector('.top-buttons button:nth-child(3)');
    
    if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
        // 退出全屏
        container.classList.remove('fullscreen');
        fullscreenButton.textContent = '全屏';
        isFullscreen = false;
        
        // 退出全屏后重新布局
        setTimeout(() => {
            fetchHomeworkAndLabels();
        }, 300);
    } else {
        // 进入全屏
        container.classList.add('fullscreen');
        fullscreenButton.textContent = '退出全屏';
        isFullscreen = true;
    }
}

// 应用隐藏过期作业功能
function applyHideExpired() {
    const hideExpired = document.getElementById("hideExpired").checked;
    const homeworkItems = document.querySelectorAll(".homework-item");
    if (!hideExpired) {
        homeworkItems.forEach(item => {
            item.style.display = "block";
        });
        return;
    }
    const now = new Date();
    homeworkItems.forEach(item => {
        const deadlineStr = item.getAttribute("data-deadline");
        const deadline = new Date(deadlineStr);
        if (deadline < now) {
            item.style.display = "none";
        }
    });
}

// 获取日期对应的星期几
function getWeekday(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return weekdays[date.getDay()];
}

// 创建作业项
function createHomeworkItem(submission) {
    const homeworkItem = document.createElement('li');
    homeworkItem.className = 'homework-item';
    homeworkItem.setAttribute('data-deadline', submission.deadline);

    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'content-wrapper';

    const contentSpan = document.createElement('span');
    contentSpan.className = 'content';
    contentSpan.innerHTML = submission.content.replace(/\r\n/g, '<br>').replace(/\n/g, '<br>').replace(/\r/g, '<br>');
    contentWrapper.appendChild(contentSpan);

    const labelsSpan = document.createElement('span');
    labelsSpan.className = 'labels';
    
    // 优先使用label_ids，如果不存在则回退到labels
    let labelNames = [];
    if (submission.label_ids && Array.isArray(submission.label_ids)) {
        // 根据ID查找标签名称
        labelNames = submission.label_ids.map(labelId => {
            const labelObj = globalLabels.find(l => l.id === labelId);
            return labelObj ? labelObj.name : '未知标签';
        });
    } else if (submission.labels && Array.isArray(submission.labels)) {
        // 回退到使用标签名称
        labelNames = submission.labels;
    }
    
    labelNames.forEach(labelName => {
        const labelTag = document.createElement('span');
        labelTag.className = 'label-tag';
        labelTag.textContent = labelName;
        const labelObj = globalLabels.find(l => l.name === labelName);
        if (labelObj) {
            labelTag.style.backgroundColor = labelObj.color;
        }
        labelsSpan.appendChild(labelTag);
    });
    
    contentWrapper.appendChild(labelsSpan);
    homeworkItem.appendChild(contentWrapper);

    const datesContainer = document.createElement('div');
    datesContainer.className = 'dates-container';

    const deadlineDiv = document.createElement('div');
    deadlineDiv.className = 'deadline';
    
    // 检查设置并添加编辑按钮
    const EditButton = getCookie("EditButton") === "true";
    if (EditButton && submission.id) {
        const editButton = document.createElement('button');
        editButton.className = 'edit-button';
        const editIcon = document.createElement('i');
        editIcon.className = 'fas fa-edit'; // 改为fas类前缀
        editButton.appendChild(editIcon);
        editButton.title = '编辑作业';
        editButton.onclick = function() {
            window.open('/homework/edit/' + submission.id, '_blank');
        };
        deadlineDiv.appendChild(editButton);
    }

    // 检查设置并添加删除按钮
    const DeleteButton = getCookie("DeleteButton") === "true";
    if (DeleteButton && submission.id) {
        const deleteButton = document.createElement('button'); // 创建删除按钮
        deleteButton.className = 'delete-button'; // 添加样式
        const deleteIcon = document.createElement('i'); // 创建图标元素
        deleteIcon.className = 'far fa-trash-alt'; // 添加图标类
        deleteButton.appendChild(deleteIcon); // 将图标添加到按钮
        deleteButton.title = '删除作业';
        deleteButton.onclick = function() {
            window.open('/homework/delete_confirm/' + submission.id, '_blank');
        };
        deadlineDiv.appendChild(deleteButton);
    }
    
    // 根据截止日期设置不同颜色类
    let deadlineText;
    if (submission.deadline) {
        const deadlineDate = new Date(submission.deadline);
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        
        // 将时间部分设置为0，只比较日期
        deadlineDate.setHours(0, 0, 0, 0);
        today.setHours(0, 0, 0, 0);
        tomorrow.setHours(0, 0, 0, 0);
        
        if (deadlineDate < today) {
            // 截止日期已过，黑色显示
            deadlineText = '截止日期: ' + submission.deadline.substring(5) + ' (' + getWeekday(submission.deadline) + ')';
            deadlineDiv.classList.add('deadline-overdue');
        } else if (deadlineDate.getTime() === today.getTime()) {
            // 截止日期为今天，红色显示
            deadlineText = '截止日期: ' + submission.deadline.substring(5) + ' (' + getWeekday(submission.deadline) + ')';
            deadlineDiv.classList.add('deadline-today');
        } else if (deadlineDate.getTime() === tomorrow.getTime()) {
            // 截止日期为明天，黄色显示
            deadlineText = '截止日期: ' + submission.deadline.substring(5) + ' (' + getWeekday(submission.deadline) + ')';
            deadlineDiv.classList.add('deadline-future');
        } else {
            // 截止日期为后天或之后，黄色显示
            deadlineText = '截止日期: ' + submission.deadline.substring(5) + ' (' + getWeekday(submission.deadline) + ')';
            deadlineDiv.classList.add('deadline-future');
        }
    } else {
        // 未设置截止日期，绿色显示
        deadlineText = '截止日期: 未设置';
        deadlineDiv.classList.add('deadline-unset');
    }
    
    const deadlineTextNode = document.createTextNode(deadlineText);
    deadlineDiv.appendChild(deadlineTextNode);
    datesContainer.appendChild(deadlineDiv);

    const timestampDiv = document.createElement('div');
    timestampDiv.className = 'timestamp';
    timestampDiv.textContent = '发布时间: ' + submission.timestamp.substring(5, 16);
    datesContainer.appendChild(timestampDiv);

    homeworkItem.appendChild(datesContainer);
    return homeworkItem;
}

// 快捷布置作业相关函数 - 重写版本
let quickPublishEnabled = false;
let subjectsData = [];
let labelsData = [];

// 显示快捷布置按钮
function showQuickPublishButton() {
    let button = document.getElementById('quickPublishFloatButton');
    if (!button) {
        button = document.createElement('button');
        button.id = 'quickPublishFloatButton';
        button.className = 'quick-publish-float-button';
        button.innerHTML = '<i class="fas fa-plus"></i>';
        button.onclick = function() {
            // 只打开第一个弹窗
            openQuickPublishModal();
        };
        document.body.appendChild(button);
    }
    button.style.display = 'block';
}

// 隐藏快捷布置按钮
function hideQuickPublishButton() {
    const button = document.getElementById('quickPublishFloatButton');
    if (button) {
        button.style.display = 'none';
    }
}

// 加载学科和标签数据
function loadQuickPublishData() {
    // 加载学科数据
    fetch('/api/subjects')
        .then(response => response.json())
        .then(subjects => {
            subjectsData = subjects;
        })
        .catch(error => {
            console.error('加载学科数据失败:', error);
        });
    
    // 加载标签数据
    fetch('/api/homework')
        .then(response => response.json())
        .then(data => {
            labelsData = data.labels || [];
        })
        .catch(error => {
            console.error('加载标签数据失败:', error);
        });
}

// 打开第一个快捷布置弹窗
function openQuickPublishModal() {
    // 如果当前是全屏模式，先退出全屏
    if (isFullscreen) {
        exitFullscreen();
    }
    
    const modal = document.getElementById("quickPublishModal");
    modal.style.display = "block";
    
    // 重置表单
    document.getElementById("quickPublishForm").reset();
    document.getElementById("quickDeadline").style.display = "none";
    
    // 取消所有标签选择
    const checkboxes = document.querySelectorAll('#quickLabelsContainer .label-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // 加载当前学科的常用词
    const currentSubject = document.getElementById('quickSubject').value;
    loadCommonWordsGrid('commonWordsGrid', currentSubject);
    
    // 确保弹窗可见并重新初始化选择框
    setTimeout(() => {
        modal.scrollTop = 0;
        initSubjectSelects();
        initSubjectChangeListeners();
    }, 10);
}

// 关闭第一个快捷布置弹窗
function closeQuickPublishModal() {
    document.getElementById("quickPublishModal").style.display = "none";
}

// 打开第二个快捷布置弹窗
function openQuickPublishModal2() {
    // 如果当前是全屏模式，先退出全屏
    if (isFullscreen) {
        exitFullscreen();
    }
    
    const modal = document.getElementById("quickPublishModal2");
    modal.style.display = "block";
    
    // 重置表单
    document.getElementById("quickPublishForm2").reset();
    document.getElementById("quickDeadline2").style.display = "none";
    
    // 取消所有标签选择
    const checkboxes = document.querySelectorAll('#quickLabelsContainer2 .label-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // 加载当前学科的常用词
    const currentSubject = document.getElementById('quickSubject2').value;
    loadCommonWordsGrid('commonWordsGrid2', currentSubject);
    
    // 确保弹窗可见并重新初始化选择框
    setTimeout(() => {
        modal.scrollTop = 0;
        initSubjectSelects();
        initSubjectChangeListeners();
    }, 10);
}

// 关闭第二个快捷布置弹窗
function closeQuickPublishModal2() {
    document.getElementById("quickPublishModal2").style.display = "none";
}

// 添加从第一个弹窗打开第二个弹窗的函数
function openSecondModalFromFirst() {
    // 在移动设备上，关闭第一个再打开第二个
    if (window.innerWidth <= 1023) {
        closeQuickPublishModal();
        setTimeout(() => {
            openQuickPublishModal2();
        }, 300);
    } else {
        // 在横屏设备上，直接打开第二个
        openQuickPublishModal2();
    }
}

// 添加从第二个弹窗打开第一个弹窗的函数
function openFirstModalFromSecond() {
    // 在移动设备上，关闭第二个再打开第一个
    if (window.innerWidth <= 1023) {
        closeQuickPublishModal2();
        setTimeout(() => {
            openQuickPublishModal();
        }, 300);
    } else {
        // 在横屏设备上，直接打开第一个
        openQuickPublishModal();
    }
}

function initSubjectSelects() {
    const subjectSelects = document.querySelectorAll('.subject-select');
    subjectSelects.forEach(select => {
        // 只添加必要的事件处理，不阻止默认行为
        select.addEventListener('mousedown', function(e) {
            e.stopPropagation();
        });
        
        select.addEventListener('touchstart', function(e) {
            e.stopPropagation();
        });
        
        // 移除可能干扰选择框正常行为的事件监听器
    });
}

// 初始化快捷发布表单
function initQuickPublishForm(formId) {
    const form = document.getElementById(formId);
    
    // 为所有输入元素添加触屏优化
    const inputs = form.querySelectorAll('input, select, textarea, button');
    inputs.forEach(input => {
        input.addEventListener('touchstart', function(e) {
            e.stopPropagation();
        });
        
        input.addEventListener('touchend', function(e) {
            e.stopPropagation();
        });
    });
}

// 加载常用词宫格
function loadCommonWordsGrid(gridId, subjectName) {
    const container = document.getElementById(gridId);
    if (!container) {
        console.error('常用词容器未找到:', gridId);
        return;
    }
    
    console.log(`开始加载学科"${subjectName}"的常用词，容器: ${gridId}...`);
    container.innerHTML = '<div class="no-words-hint">加载中...</div>';
    
    // 获取科目常用词和通用常用词
    Promise.all([
        getSubjectCommonWords(subjectName),
        getGlobalCommonWords()
    ]).then(([subjectWords, globalWords]) => {
        console.log(`学科"${subjectName}"专用词:`, subjectWords);
        console.log(`通用常用词:`, globalWords);
        displayWordsGrid(subjectWords, globalWords, gridId);
    }).catch((error) => {
        console.error('加载常用词失败:', error);
        // 使用默认常用词
        const defaultSubjectWords = getDefaultSubjectWords(subjectName);
        const defaultGlobalWords = ['作业', '试卷', '背诵', '默写', '作文', '笔记'];
        displayWordsGrid(defaultSubjectWords, defaultGlobalWords, gridId);
    });
}

// 获取科目常用词
function getSubjectCommonWords(subjectName) {
    return fetch('/api/subjects')
        .then(response => {
            if (!response.ok) throw new Error('Network error');
            return response.json();
        })
        .then(subjects => {
            // 查找匹配的学科
            const subject = subjects.find(s => s.name === subjectName);
            
            if (subject) {
                // 直接返回学科的 common_words 字段
                const commonWords = subject.common_words || [];
                console.log(`学科"${subjectName}"的常用词:`, commonWords);
                return commonWords;
            } else {
                // 如果没有找到学科，使用默认的学科常用词
                const defaultWords = getDefaultSubjectWords(subjectName);
                console.log(`学科"${subjectName}"未找到，使用默认词:`, defaultWords);
                return defaultWords;
            }
        })
        .catch((error) => {
            console.error(`获取学科"${subjectName}"常用词失败:`, error);
            // 出错时返回默认常用词
            return getDefaultSubjectWords(subjectName);
        });
}

// 获取默认的学科常用词
function getDefaultSubjectWords(subjectName) {
    const defaultWords = {
        '语文': ['朗读', '背诵', '默写', '作文', '阅读', '预习', '复习', '生字', '词语', '课文'],
        '数学': ['练习', '计算', '习题', '预习', '复习', '作业本', '试卷', '口算', '应用题', '几何'],
        '英语': ['朗读', '背诵', '默写', '作文', '阅读', '单词', '语法', '听力', '口语', '预习'],
        '物理': ['实验', '习题', '预习', '复习', '公式', '计算', '概念', '作业本', '试卷'],
        '化学': ['实验', '方程式', '预习', '复习', '元素', '反应', '作业本', '试卷'],
        '生物': ['实验', '预习', '复习', '概念', '图表', '作业本', '试卷'],
        '历史': ['预习', '复习', '背诵', '时间线', '事件', '作业本', '试卷'],
        '地理': ['预习', '复习', '地图', '概念', '作业本', '试卷'],
        '政治': ['预习', '复习', '背诵', '概念', '作业本', '试卷']
    };
    
    return defaultWords[subjectName] || ['练习', '复习', '预习', '作业'];
}

// 获取通用常用词
function getGlobalCommonWords() {
    return fetch('/api/global_words')
        .then(response => {
            if (!response.ok) throw new Error('Network error');
            return response.json();
        })
        .catch(() => []);
}

// 显示常用词宫格
function displayWordsGrid(subjectWords, globalWords, gridId) {
    const container = document.getElementById(gridId);
    container.innerHTML = '';
    container.className = 'common-words-container';
    
    console.log(`显示宫格 - 学科词: ${subjectWords.length}个, 通用词: ${globalWords.length}个`); // 调试信息
    
    // 创建学科专用词区域
    if (subjectWords && subjectWords.length > 0) {
        const subjectSection = createWordsSection('subject', subjectWords, '学科专用词', gridId);
        container.appendChild(subjectSection);
    } else {
        console.log(`学科"${document.getElementById(gridId === 'commonWordsGrid2' ? 'quickSubject2' : 'quickSubject').value}"没有专用词`); // 调试信息
    }
    
    // 创建通用常用词区域
    if (globalWords && globalWords.length > 0) {
        const globalSection = createWordsSection('global', globalWords, '通用常用词', gridId);
        container.appendChild(globalSection);
    }
    
    // 如果都没有词，显示提示
    if ((!subjectWords || subjectWords.length === 0) && (!globalWords || globalWords.length === 0)) {
        const noWordsHint = document.createElement('div');
        noWordsHint.className = 'no-words-hint';
        noWordsHint.textContent = '暂无常用词，可在设置中添加';
        noWordsHint.style.gridColumn = '1 / -1';
        container.appendChild(noWordsHint);
    }
}

// 创建词条区域
function createWordsSection(type, words, title, gridId) {
    const section = document.createElement('div');
    section.className = `words-section ${type}-words-section`;
    
    // 添加标题
    const titleElement = document.createElement('div');
    titleElement.className = 'section-title';
    titleElement.textContent = `${title} (${words.length})`;
    section.appendChild(titleElement);
    
    // 创建网格容器
    const grid = document.createElement('div');
    grid.className = 'words-grid';
    
    // 添加词条按钮
    words.forEach(word => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `word-grid-btn ${type}-word`;
        button.title = word;
        button.textContent = word.length > 4 ? word.substring(0, 4) + '...' : word;
        
        // 点击事件
        button.onclick = function(e) {
            e.preventDefault();
            insertWordToQuickContent(word, gridId === 'commonWordsGrid2' ? 'quickContent2' : 'quickContent');
        };
        
        // 触屏优化
        button.addEventListener('touchstart', function(e) {
            e.preventDefault();
            insertWordToQuickContent(word, gridId === 'commonWordsGrid2' ? 'quickContent2' : 'quickContent');
        });
        
        grid.appendChild(button);
    });
    
    section.appendChild(grid);
    return section;
}

// 初始化学科变更监听
function initSubjectChangeListeners() {
    const subjectSelect1 = document.getElementById('quickSubject');
    const subjectSelect2 = document.getElementById('quickSubject2');
    
    if (subjectSelect1) {
        // 移除可能存在的旧监听器
        const newSelect1 = subjectSelect1.cloneNode(true);
        subjectSelect1.parentNode.replaceChild(newSelect1, subjectSelect1);
        
        // 重新添加事件监听
        document.getElementById('quickSubject').addEventListener('change', function() {
            console.log('学科选择变化:', this.value);
            loadCommonWordsGrid('commonWordsGrid', this.value);
        });
    }
    
    if (subjectSelect2) {
        // 移除可能存在的旧监听器
        const newSelect2 = subjectSelect2.cloneNode(true);
        subjectSelect2.parentNode.replaceChild(newSelect2, subjectSelect2);
        
        // 重新添加事件监听
        document.getElementById('quickSubject2').addEventListener('change', function() {
            console.log('学科选择变化2:', this.value);
            loadCommonWordsGrid('commonWordsGrid2', this.value);
        });
    }
    
    // 添加全局事件委托，确保动态创建的选择框也能工作
    document.addEventListener('change', function(e) {
        if (e.target && (e.target.id === 'quickSubject' || e.target.id === 'quickSubject2')) {
            const gridId = e.target.id === 'quickSubject' ? 'commonWordsGrid' : 'commonWordsGrid2';
            console.log('全局事件捕获到学科变化:', e.target.value, 'grid:', gridId);
            loadCommonWordsGrid(gridId, e.target.value);
        }
    });
}

// 插入词语到内容
function insertWordToQuickContent(word, contentId) {
    const content = document.getElementById(contentId);
    const start = content.selectionStart;
    const end = content.selectionEnd;
    const text = content.value;
    
    content.value = text.substring(0, start) + word + text.substring(end);
    content.focus();
    content.selectionStart = content.selectionEnd = start + word.length;
    
    // 触发输入事件以更新UI
    const event = new Event('input', { bubbles: true });
    content.dispatchEvent(event);
}

// 设置快捷日期
function setQuickDate(type) {
    const dateInput = document.getElementById('quickDeadline');
    const today = new Date();
    
    switch(type) {
        case 'today':
            dateInput.value = today.toISOString().split('T')[0];
            dateInput.style.display = 'block';
            break;
        case 'tomorrow':
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            dateInput.value = tomorrow.toISOString().split('T')[0];
            dateInput.style.display = 'block';
            break;
        case 'custom':
            dateInput.style.display = 'block';
            dateInput.focus();
            break;
    }
}

// 第二个弹窗的日期设置
function setQuickDate2(type) {
    const dateInput = document.getElementById('quickDeadline2');
    const today = new Date();
    
    switch(type) {
        case 'today':
            dateInput.value = today.toISOString().split('T')[0];
            dateInput.style.display = 'block';
            break;
        case 'tomorrow':
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            dateInput.value = tomorrow.toISOString().split('T')[0];
            dateInput.style.display = 'block';
            break;
        case 'custom':
            dateInput.style.display = 'block';
            dateInput.focus();
            break;
    }
}

// 清空日期
function clearQuickDate() {
    document.getElementById('quickDeadline').value = '';
    document.getElementById('quickDeadline').style.display = 'none';
}

function clearQuickDate2() {
    document.getElementById('quickDeadline2').value = '';
    document.getElementById('quickDeadline2').style.display = 'none';
}

// 提交快捷布置作业
function submitQuickPublish() {
    const subject = document.getElementById('quickSubject').value;
    const content = document.getElementById('quickContent').value.trim();
    const deadline = document.getElementById('quickDeadline').value;
    
    // 获取选中的标签
    const selectedLabels = [];
    const checkboxes = document.querySelectorAll('#quickLabelsContainer .label-checkbox:checked');
    checkboxes.forEach(checkbox => {
        selectedLabels.push(checkbox.value);
    });
    
    if (!subject) {
        alert('请选择学科');
        return;
    }
    
    if (!content) {
        alert('请输入作业内容');
        document.getElementById('quickContent').focus();
        return;
    }
    
    // 构建表单数据
    const formData = new FormData();
    formData.append('subject', subject);
    formData.append('content', content);
    if (deadline) {
        formData.append('deadline', deadline);
    }
    selectedLabels.forEach(labelId => {
        formData.append('label_ids', labelId);
    });
    
    // 添加确认标记，跳过确认页面直接提交
    formData.append('confirm', 'true');
    
    console.log('提交数据:', {
        subject: subject,
        content: content,
        deadline: deadline,
        labels: selectedLabels
    });
    
    // 提交数据 - 使用标准的表单提交方式
    fetch('/homework/publish', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest' // 添加 AJAX 标识
        }
    })
    .then(response => {
        // 检查响应类型
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return response.json();
        } else {
            // 如果不是 JSON，可能是重定向或 HTML
            if (response.redirected) {
                return { success: true, redirected: true };
            }
            return response.text().then(text => {
                console.log('响应文本:', text);
                throw new Error('服务器返回了非JSON响应');
            });
        }
    })
    .then(data => {
        console.log('响应数据:', data);
        if (data.success || data.redirected) {
            alert('作业发布成功！');
            closeQuickPublishModal();
            // 刷新作业列表
            fetchHomeworkAndLabels();
        } else {
            alert('发布失败：' + (data.message || '未知错误'));
        }
    })
    .catch(error => {
        console.error('提交错误:', error);
        // 如果是重定向导致的错误，也认为是成功
        if (error.message.includes('redirect')) {
            alert('作业发布成功！');
            closeQuickPublishModal();
            fetchHomeworkAndLabels();
        } else {
            alert('发布失败，请检查网络连接后重试。错误信息: ' + error.message);
        }
    });
}

// 提交第二个弹窗的作业
function submitQuickPublish2() {
    const subject = document.getElementById('quickSubject2').value;
    const content = document.getElementById('quickContent2').value.trim();
    const deadline = document.getElementById('quickDeadline2').value;
    
    // 获取选中的标签
    const selectedLabels = [];
    const checkboxes = document.querySelectorAll('#quickLabelsContainer2 .label-checkbox:checked');
    checkboxes.forEach(checkbox => {
        selectedLabels.push(checkbox.value);
    });
    
    if (!subject) {
        alert('请选择学科');
        return;
    }
    
    if (!content) {
        alert('请输入作业内容');
        document.getElementById('quickContent2').focus();
        return;
    }
    
    // 构建表单数据
    const formData = new FormData();
    formData.append('subject', subject);
    formData.append('content', content);
    if (deadline) {
        formData.append('deadline', deadline);
    }
    selectedLabels.forEach(labelId => {
        formData.append('label_ids', labelId);
    });
    
    // 添加确认标记，跳过确认页面直接提交
    formData.append('confirm', 'true');
    
    console.log('提交数据2:', {
        subject: subject,
        content: content,
        deadline: deadline,
        labels: selectedLabels
    });
    
    // 提交数据
    fetch('/homework/publish', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return response.json();
        } else {
            if (response.redirected) {
                return { success: true, redirected: true };
            }
            return response.text().then(text => {
                console.log('响应文本2:', text);
                throw new Error('服务器返回了非JSON响应');
            });
        }
    })
    .then(data => {
        console.log('响应数据2:', data);
        if (data.success || data.redirected) {
            alert('作业发布成功！');
            closeQuickPublishModal2();
            fetchHomeworkAndLabels();
        } else {
            alert('发布失败：' + (data.message || '未知错误'));
        }
    })
    .catch(error => {
        console.error('提交错误2:', error);
        if (error.message.includes('redirect')) {
            alert('作业发布成功！');
            closeQuickPublishModal2();
            fetchHomeworkAndLabels();
        } else {
            alert('发布失败，请检查网络连接后重试。错误信息: ' + error.message);
        }
    });
}

// 添加事件监听器确保学科选择框正常工作
document.addEventListener('DOMContentLoaded', function() {
    // 为学科选择框添加额外的事件处理
    const subjectSelects = document.querySelectorAll('#quickSubject, #quickSubject2');
    subjectSelects.forEach(select => {
        // 防止事件冒泡
        select.addEventListener('mousedown', function(e) {
            e.stopPropagation();
        });
        
        select.addEventListener('touchstart', function(e) {
            e.stopPropagation();
        });
        
        select.addEventListener('click', function(e) {
            e.stopPropagation();
        });
        
        // 修复 iOS 上的选择问题
        select.addEventListener('focus', function() {
            this.style.backgroundColor = '#fff';
        });
        
        select.addEventListener('blur', function() {
            this.style.backgroundColor = '';
        });
    });
    
    // 确保模态窗口点击不会关闭
    const modals = document.querySelectorAll('#quickPublishModal .modal-content, #quickPublishModal2 .modal-content');
    modals.forEach(modal => {
        modal.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });
});

// 修改浮动按钮位置，确保始终可见
function updateFloatButtonPosition() {
    const button = document.getElementById('quickPublishFloatButton');
    if (button) {
        // 确保按钮在所有弹窗之上
        button.style.zIndex = '10003';
    }
}

// 点击模态框外部关闭（更新版）
window.onclick = function(event) {
    const settingsModal = document.getElementById("settingsModal");
    const quickPublishModal = document.getElementById("quickPublishModal");
    const quickPublishModal2 = document.getElementById("quickPublishModal2");
    
    // 如果点击的是选择框或其选项，不关闭弹窗
    if (event.target.classList.contains('subject-select') || 
        event.target.tagName === 'OPTION' ||
        event.target.closest('.subject-select')) {
        return;
    }
    
    if (event.target == settingsModal) {
        closeSettings();
    }
    if (event.target == quickPublishModal) {
        closeQuickPublishModal();
    }
    if (event.target == quickPublishModal2) {
        closeQuickPublishModal2();
    }
}

// 触屏设备的外部点击关闭支持
document.addEventListener('touchstart', function(event) {
    const settingsModal = document.getElementById("settingsModal");
    const quickPublishModal = document.getElementById("quickPublishModal");
    const quickPublishModal2 = document.getElementById("quickPublishModal2");
    
    // 检查是否点击了模态框内容区域，如果是则不要关闭
    if (event.target.closest('.modal-content')) {
        return;
    }
    
    if (event.target === settingsModal) {
        closeSettings();
    }
    if (event.target === quickPublishModal) {
        closeQuickPublishModal();
    }
    if (event.target === quickPublishModal2) {
        closeQuickPublishModal2();
    }
});

// 处理窗口大小变化
function handleWindowResize() {
    const modal1 = document.getElementById("quickPublishModal");
    const modal2 = document.getElementById("quickPublishModal2");
    
    // 如果从横屏切换到竖屏且两个窗口都打开，关闭第二个窗口
    if (window.innerWidth <= 1023 && modal1.style.display === "block" && modal2.style.display === "block") {
        closeQuickPublishModal2();
    }
}