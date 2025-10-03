let refreshInterval;
let intervalId;
let isFullscreen = false;
let globalLabels = []; // 全局标签缓存

// 快捷布置作业相关变量
let quickPublishEnabled = false;
let subjectsData = [];
let labelsData = [];

// 窗口大小变化时重新布局
let resizeTimeout;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        fetchHomeworkAndLabels();
    }, 250);
});

// 页面加载完成后初始化
window.onload = function() {
    loadSettings();
    startAutoRefresh();
    applyHideExpired();
    loadQuickPublishData();
};

// 加载设置（从cookie）
function loadSettings() {
    const savedInterval = getCookie("refreshInterval");
    if (savedInterval) {
        refreshInterval = parseInt(savedInterval);
        document.getElementById("refreshInterval").value = refreshInterval;
    } else {
        refreshInterval = 60;
    }
    const savedFontSize = getCookie("fontSize");
    if (savedFontSize) {
        document.body.style.fontSize = savedFontSize + 'px';
        document.getElementById("fontSize").value = savedFontSize;
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
    if (newInterval >= 10 && newInterval <= 3600) {
        refreshInterval = parseInt(newInterval);
        setCookie("refreshInterval", refreshInterval, 30);
        if (intervalId) clearInterval(intervalId);
        startAutoRefresh();
    } else {
        alert('刷新间隔必须在10-3600秒之间');
        return;
    }
    const fontSize = document.getElementById("fontSize").value;
    document.body.style.fontSize = fontSize + 'px';
    setCookie("fontSize", fontSize, 30);
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

// 计算最大列高度（更精确的版本）
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
    
    // 减少容器边距和安全边距
    const containerMargin = 15; // 减少容器边距
    const safetyMargin = 15; // 减少安全边距
    
    // 返回可用高度（减少保守程度）
    return Math.max(200, screenHeight - totalFixedHeight - containerMargin - safetyMargin);
}

// 计算作业项的实际估算高度（更准确的版本）
function calculateItemHeight(submission) {
    const bodyStyle = getComputedStyle(document.body);
    const currentFontSize = parseFloat(bodyStyle.fontSize);
    const baseFontSize = 16;
    const fontScale = currentFontSize / baseFontSize;
    
    // 基础结构高度（减少基础高度）
    const baseStructureHeight = Math.ceil(75 * fontScale); // 从95减少到75
    
    // 内容高度估算（更准确的行数计算）
    const content = submission.content || '';
    const charsPerLine = Math.max(15, Math.floor(22 / fontScale)); // 增加每行字符数
    const lineHeight = Math.ceil(18 * fontScale); // 减少行高
    const contentLines = Math.max(1, Math.ceil(content.length / charsPerLine));
    const contentHeight = Math.ceil(contentLines * lineHeight);
    
    // 标签高度
    const labelCount = (submission.labels && submission.labels.length) || 
                      (submission.label_ids && submission.label_ids.length) || 0;
    const labelHeight = labelCount > 0 ? Math.ceil(22 * fontScale) : 0; // 减少标签高度
    
    // 内边距、边框和间距（减少这些值）
    const paddingAndBorder = Math.ceil(15 * fontScale); // 从20减少到15
    const itemSpacing = Math.ceil(5 * fontScale); // 从8减少到5
    
    // 总高度（使用更准确的估算，减少安全边距）
    const totalHeight = baseStructureHeight + contentHeight + labelHeight + 
                        paddingAndBorder + itemSpacing;
    
    return Math.ceil(totalHeight);
}

// 计算学科标题的高度（更准确的版本）
function calculateSubjectTitleHeight() {
    const bodyStyle = getComputedStyle(document.body);
    const currentFontSize = parseFloat(bodyStyle.fontSize);
    const baseFontSize = 16;
    const fontScale = currentFontSize / baseFontSize;
    
    // 学科标题的基础高度（减少估算）
    const baseTitleHeight = Math.ceil(35 * fontScale); // 从45减少到35
    const titlePadding = Math.ceil(12 * fontScale); // 从18减少到12
    const titleMargin = Math.ceil(8 * fontScale); // 从10减少到8
    
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
        
        subjectItems.forEach((item, index) => {
            let targetColumn = findTargetColumn(columnHeights, item.estimatedHeight, maxColumnHeight, subjectStartColumn);
            
            // 如果找不到合适的列，使用最后一列（必须放置）
            if (targetColumn === -1) {
                targetColumn = colCount - 1;
            }
            
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

// 找到目标列（修复版本）
function findTargetColumn(columnHeights, itemHeight, maxHeight, subjectStartColumn) {
    // 优先尝试从学科开始的列开始
    if (subjectStartColumn !== -1) {
        for (let i = subjectStartColumn; i < columnHeights.length; i++) {
            if (columnHeights[i] + itemHeight <= maxHeight) {
                return i;
            }
        }
    }
    
    // 如果学科开始的列不合适，从头开始找
    for (let i = 0; i < columnHeights.length; i++) {
        if (columnHeights[i] + itemHeight <= maxHeight) {
            return i;
        }
    }
    
    // 如果所有列都放不下，返回最后一列
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
    document.getElementById("settingsModal").style.display = "block";
}

// 关闭设置弹窗
function closeSettings() {
    document.getElementById("settingsModal").style.display = "none";
}

// 切换全屏模式
function toggleFullscreen() {
    const container = document.querySelector('.container');
    isFullscreen = !isFullscreen;
    if (isFullscreen) {
        container.classList.add('fullscreen');
        document.querySelector('.top-buttons button:nth-child(3)').textContent = '退出全屏';
    } else {
        container.classList.remove('fullscreen');
        document.querySelector('.top-buttons button:nth-child(3)').textContent = '全屏';
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

// 点击模态框外部关闭
window.onclick = function(event) {
    const modal = document.getElementById("settingsModal");
    if (event.target == modal) {
        closeSettings();
    }
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
    contentSpan.textContent = submission.content;
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
    
    const deadlineText = submission.deadline ? 
        '截止日期: ' + submission.deadline.substring(5) + ' (' + getWeekday(submission.deadline) + ')' : 
        '截止日期: 未设置';
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

// 显示快捷布置按钮
function showQuickPublishButton() {
    let button = document.getElementById('quickPublishFloatButton');
    if (!button) {
        button = document.createElement('button');
        button.id = 'quickPublishFloatButton';
        button.className = 'quick-publish-float-button';
        button.innerHTML = '<i class="fas fa-plus"></i>';
        button.onclick = openQuickPublishModal;
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
        });
    
    // 加载标签数据
    fetch('/api/homework')
        .then(response => response.json())
        .then(data => {
            labelsData = data.labels || [];
        });
}

// 打开第一个快捷布置弹窗
function openQuickPublishModal() {
    document.getElementById("quickPublishModal").style.display = "block";
    loadCommonWordsGrid('commonWordsGrid');
    initMultiSelect('quickLabels');
}

// 关闭第一个快捷布置弹窗
function closeQuickPublishModal() {
    document.getElementById("quickPublishModal").style.display = "none";
    document.getElementById("quickPublishForm").reset();
}

// 打开第二个快捷布置弹窗
function openQuickPublishModal2() {
    document.getElementById("quickPublishModal2").style.display = "block";
    loadCommonWordsGrid('commonWordsGrid2');
    initMultiSelect('quickLabels2');
}

// 关闭第二个快捷布置弹窗
function closeQuickPublishModal2() {
    document.getElementById("quickPublishModal2").style.display = "none";
    document.getElementById("quickPublishForm2").reset();
}

// 加载常用词宫格
function loadCommonWordsGrid(gridId) {
    const grid = document.getElementById(gridId);
    grid.innerHTML = '';
    
    // 获取通用常用词
    fetch('/api/global_words')
        .then(response => response.json())
        .then(words => {
            // 创建3x3宫格
            for (let i = 0; i < Math.min(9, words.length); i++) {
                const word = words[i];
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'word-grid-btn';
                button.textContent = word;
                button.onclick = function() {
                    insertWordToQuickContent(word, gridId === 'commonWordsGrid2' ? 'quickContent2' : 'quickContent');
                };
                grid.appendChild(button);
            }
        })
        .catch(() => {
            // 备用方案：使用默认常用词
            const defaultWords = ['练习', '复习', '预习', '作业', '试卷', '背诵', '默写', '作文', '笔记'];
            defaultWords.forEach(word => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'word-grid-btn';
                button.textContent = word;
                button.onclick = function() {
                    insertWordToQuickContent(word, gridId === 'commonWordsGrid2' ? 'quickContent2' : 'quickContent');
                };
                grid.appendChild(button);
            });
        });
}

// 初始化多选下拉框
function initMultiSelect(selectId) {
    const select = document.getElementById(selectId);
    // 简单的多选实现
    select.addEventListener('mousedown', function(e) {
        e.preventDefault();
        const option = e.target;
        if (option.tagName === 'OPTION') {
            option.selected = !option.selected;
        }
    });
    
    // 触屏设备支持
    select.addEventListener('touchstart', function(e) {
        e.preventDefault();
        const option = e.target;
        if (option.tagName === 'OPTION') {
            option.selected = !option.selected;
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
}

// 设置快捷日期
function setQuickDate(type) {
    const dateInput = document.getElementById('quickDeadline');
    const today = new Date();
    
    switch(type) {
        case 'today':
            dateInput.value = today.toISOString().split('T')[0];
            dateInput.style.display = 'none';
            break;
        case 'tomorrow':
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            dateInput.value = tomorrow.toISOString().split('T')[0];
            dateInput.style.display = 'none';
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
            dateInput.style.display = 'none';
            break;
        case 'tomorrow':
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            dateInput.value = tomorrow.toISOString().split('T')[0];
            dateInput.style.display = 'none';
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
    const content = document.getElementById('quickContent').value;
    const deadline = document.getElementById('quickDeadline').value;
    const labelSelect = document.getElementById('quickLabels');
    const selectedLabels = Array.from(labelSelect.selectedOptions).map(option => option.value);
    
    if (!content.trim()) {
        alert('请输入作业内容');
        return;
    }
    
    // 提交数据
    const formData = new FormData();
    formData.append('subject', subject);
    formData.append('content', content);
    formData.append('deadline', deadline);
    selectedLabels.forEach(labelId => {
        formData.append('label_ids', labelId);
    });
    
    fetch('/homework/publish', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('作业发布成功！');
            closeQuickPublishModal();
            // 刷新作业列表
            fetchHomeworkAndLabels();
        } else {
            alert('发布失败：' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('发布失败，请重试');
    });
}

// 提交第二个弹窗的作业
function submitQuickPublish2() {
    const subject = document.getElementById('quickSubject2').value;
    const content = document.getElementById('quickContent2').value;
    const deadline = document.getElementById('quickDeadline2').value;
    const labelSelect = document.getElementById('quickLabels2');
    const selectedLabels = Array.from(labelSelect.selectedOptions).map(option => option.value);
    
    if (!content.trim()) {
        alert('请输入作业内容');
        return;
    }
    
    // 提交数据
    const formData = new FormData();
    formData.append('subject', subject);
    formData.append('content', content);
    formData.append('deadline', deadline);
    selectedLabels.forEach(labelId => {
        formData.append('label_ids', labelId);
    });
    
    fetch('/homework/publish', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('作业发布成功！');
            closeQuickPublishModal2();
            // 刷新作业列表
            fetchHomeworkAndLabels();
        } else {
            alert('发布失败：' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('发布失败，请重试');
    });
}