// 应用状态
let currentChapter = null;
let tocItems = [];

// DOM元素
const elements = {
    sidebar: document.getElementById('sidebar'),
    sidebarToggle: document.getElementById('sidebarToggle'),
    mobileMenuBtn: document.getElementById('mobileMenuBtn'),
    overlay: document.getElementById('overlay'),
    mainContent: document.getElementById('mainContent'),
    content: document.getElementById('content'),
    chapterList: document.getElementById('chapterList'),
    searchInput: document.getElementById('searchInput'),
    searchClear: document.getElementById('searchClear'),
    themeToggle: document.getElementById('themeToggle'),
    navPrev: document.getElementById('navPrev'),
    navNext: document.getElementById('navNext'),
    backToTop: document.getElementById('backToTop'),
};

// 初始化marked配置
function initMarked() {
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (e) {}
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: false,
        gfm: true,
    });
}

// 初始化章节列表
function initChapterList() {
    const listHTML = chapters.map((chapter, index) => `
        <li class="chapter-item">
            <a class="chapter-link" data-id="${chapter.id}" data-index="${index}" href="#${chapter.dir}">
                <span class="chapter-number">${chapter.id}</span>
                <span class="chapter-title">${chapter.title}</span>
            </a>
            <ul class="toc-list" id="toc-${chapter.id}"></ul>
        </li>
    `).join('');
    
    elements.chapterList.innerHTML = listHTML;
    
    // 添加点击事件
    elements.chapterList.addEventListener('click', (e) => {
        const link = e.target.closest('.chapter-link');
        if (link) {
            e.preventDefault();
            const chapterId = link.dataset.id;
            loadChapter(chapterId);
            
            // 移动端关闭侧边栏
            if (window.innerWidth <= 768) {
                closeSidebar();
            }
        }
    });
}

// 加载章节内容
async function loadChapter(chapterId) {
    const chapter = chapters.find(c => c.id === chapterId);
    if (!chapter) return;
    
    currentChapter = chapterId;
    
    // 更新活动状态
    updateActiveChapter(chapterId);
    
    // 显示加载状态
    elements.content.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>加载中...</p>
        </div>
    `;
    
    // 更新URL
    history.pushState(null, '', `#${chapter.dir}`);
    
    try {
        const response = await fetch(`../${chapter.dir}/README.md`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        let markdown = await response.text();
        
        // 处理相对图片路径
        markdown = processImagePaths(markdown, chapter.dir);
        
        // 渲染Markdown
        const html = marked.parse(markdown);
        elements.content.innerHTML = html;
        
        // 提取目录
        extractToc(chapterId);
        
        // 添加代码复制按钮
        addCopyButtons();
        
        // 更新章节导航
        updateChapterNav(chapterId);
        
        // 滚动到顶部
        elements.mainContent.scrollTop = 0;
        
    } catch (error) {
        console.error('加载章节失败:', error);
        elements.content.innerHTML = `
            <div class="error">
                <div class="error-icon">😕</div>
                <h2>加载失败</h2>
                <p>无法加载章节内容：${error.message}</p>
                <p style="margin-top: 16px; color: var(--text-muted); font-size: 0.9rem;">
                    请确保 README.md 文件存在于 ${chapter.dir} 目录中
                </p>
            </div>
        `;
    }
}

// 处理Markdown中的相对图片路径
function processImagePaths(markdown, chapterDir) {
    return markdown.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src) => {
        // 如果是相对路径（不以http://或https://开头）
        if (!src.startsWith('http://') && !src.startsWith('https://') && !src.startsWith('/')) {
            // 转换为相对于chapter目录的路径
            const newSrc = `../${chapterDir}/${src}`;
            return `![${alt}](${newSrc})`;
        }
        return match;
    });
}

// 提取Markdown中的标题生成目录
function extractToc(chapterId) {
    const headings = elements.content.querySelectorAll('h2, h3');
    const tocContainer = document.getElementById(`toc-${chapterId}`);
    
    if (!tocContainer) return;
    
    tocItems = [];
    let tocHTML = '';
    
    headings.forEach((heading, index) => {
        const level = heading.tagName.toLowerCase();
        const id = `heading-${index}`;
        heading.id = id;
        
        const text = heading.textContent.trim();
        const isH3 = level === 'h3';
        
        tocItems.push({ id, text, level, element: heading });
        
        tocHTML += `
            <li>
                <a class="toc-link ${isH3 ? 'level-3' : ''}" data-heading="${id}" href="#${id}">
                    ${text}
                </a>
            </li>
        `;
    });
    
    tocContainer.innerHTML = tocHTML;
    tocContainer.classList.add('expanded');
    
    // 添加目录点击事件
    tocContainer.addEventListener('click', (e) => {
        const link = e.target.closest('.toc-link');
        if (link) {
            e.preventDefault();
            const headingId = link.dataset.heading;
            const heading = document.getElementById(headingId);
            if (heading) {
                heading.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    });
    
    // 添加滚动监听
    initScrollSpy();
}

// 滚动监听，高亮当前目录项
function initScrollSpy() {
    const mainContent = elements.mainContent;
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.id;
                updateActiveTocItem(id);
            }
        });
    }, {
        root: mainContent,
        rootMargin: '-80px 0px -80% 0px',
        threshold: 0
    });
    
    tocItems.forEach(item => {
        observer.observe(item.element);
    });
}

// 更新活动目录项
function updateActiveTocItem(headingId) {
    document.querySelectorAll('.toc-link').forEach(link => {
        link.classList.remove('active');
    });
    
    const activeLink = document.querySelector(`.toc-link[data-heading="${headingId}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
        // 滚动目录项到可见区域
        activeLink.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// 添加代码复制按钮
function addCopyButtons() {
    const codeBlocks = elements.content.querySelectorAll('pre');
    
    codeBlocks.forEach(pre => {
        const button = document.createElement('button');
        button.className = 'code-copy-btn';
        button.textContent = '复制';
        button.addEventListener('click', () => {
            const code = pre.querySelector('code');
            const text = code ? code.textContent : pre.textContent;
            
            navigator.clipboard.writeText(text).then(() => {
                button.textContent = '已复制';
                button.classList.add('copied');
                setTimeout(() => {
                    button.textContent = '复制';
                    button.classList.remove('copied');
                }, 2000);
            }).catch(err => {
                console.error('复制失败:', err);
                // 降级方案
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                button.textContent = '已复制';
                button.classList.add('copied');
                setTimeout(() => {
                    button.textContent = '复制';
                    button.classList.remove('copied');
                }, 2000);
            });
        });
        
        pre.style.position = 'relative';
        pre.appendChild(button);
    });
}

// 更新活动章节
function updateActiveChapter(chapterId) {
    document.querySelectorAll('.chapter-link').forEach(link => {
        link.classList.remove('active');
    });
    
    const activeLink = document.querySelector(`.chapter-link[data-id="${chapterId}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
        activeLink.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// 更新章节导航（上一章/下一章）
function updateChapterNav(chapterId) {
    const currentIndex = chapters.findIndex(c => c.id === chapterId);
    
    // 上一章
    if (currentIndex > 0) {
        const prevChapter = chapters[currentIndex - 1];
        elements.navPrev.style.display = 'flex';
        elements.navPrev.querySelector('.nav-title').textContent = prevChapter.title;
        elements.navPrev.onclick = (e) => {
            e.preventDefault();
            loadChapter(prevChapter.id);
        };
    } else {
        elements.navPrev.style.display = 'none';
    }
    
    // 下一章
    if (currentIndex < chapters.length - 1) {
        const nextChapter = chapters[currentIndex + 1];
        elements.navNext.style.display = 'flex';
        elements.navNext.querySelector('.nav-title').textContent = nextChapter.title;
        elements.navNext.onclick = (e) => {
            e.preventDefault();
            loadChapter(nextChapter.id);
        };
    } else {
        elements.navNext.style.display = 'none';
    }
}

// 搜索功能
function initSearch() {
    let searchTimeout;
    
    elements.searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            performSearch(e.target.value.trim());
        }, 300);
    });
    
    elements.searchClear.addEventListener('click', () => {
        elements.searchInput.value = '';
        performSearch('');
        elements.searchInput.focus();
    });
}

function performSearch(query) {
    const lowerQuery = query.toLowerCase();
    
    // 显示/隐藏清除按钮
    elements.searchClear.style.display = query ? 'flex' : 'none';
    
    // 过滤章节
    document.querySelectorAll('.chapter-link').forEach(link => {
        const title = link.querySelector('.chapter-title').textContent.toLowerCase();
        const chapterId = link.dataset.id;
        const chapter = chapters.find(c => c.id === chapterId);
        
        if (!query || title.includes(lowerQuery)) {
            link.classList.remove('hidden');
            // 高亮匹配文本
            if (query) {
                const titleEl = link.querySelector('.chapter-title');
                const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
                titleEl.innerHTML = chapter.title.replace(regex, '<mark>$1</mark>');
            } else {
                link.querySelector('.chapter-title').textContent = chapter.title;
            }
        } else {
            link.classList.add('hidden');
        }
    });
}

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 主题切换
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
    
    elements.themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
    });
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // 切换highlight.js主题
    const lightTheme = document.getElementById('hljs-light');
    const darkTheme = document.getElementById('hljs-dark');
    
    if (theme === 'dark') {
        lightTheme.disabled = true;
        darkTheme.disabled = false;
    } else {
        lightTheme.disabled = false;
        darkTheme.disabled = true;
    }
}

// 侧边栏控制
function initSidebar() {
    elements.sidebarToggle.addEventListener('click', () => {
        elements.sidebar.classList.toggle('collapsed');
    });
    
    elements.mobileMenuBtn.addEventListener('click', () => {
        openSidebar();
    });
    
    elements.overlay.addEventListener('click', () => {
        closeSidebar();
    });
}

function openSidebar() {
    elements.sidebar.classList.add('open');
    elements.overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeSidebar() {
    elements.sidebar.classList.remove('open');
    elements.overlay.classList.remove('active');
    document.body.style.overflow = '';
}

// 回到顶部按钮
function initBackToTop() {
    elements.mainContent.addEventListener('scroll', () => {
        if (elements.mainContent.scrollTop > 300) {
            elements.backToTop.classList.add('visible');
        } else {
            elements.backToTop.classList.remove('visible');
        }
    });
    
    elements.backToTop.addEventListener('click', () => {
        elements.mainContent.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// 从URL hash加载章节
function loadFromHash() {
    const hash = window.location.hash.slice(1);
    if (hash) {
        const chapter = chapters.find(c => c.dir === hash);
        if (chapter) {
            loadChapter(chapter.id);
            return;
        }
    }
    // 默认加载第一章
    if (chapters.length > 0) {
        loadChapter(chapters[0].id);
    }
}

// 监听hash变化
window.addEventListener('popstate', () => {
    loadFromHash();
});

// 键盘快捷键
function initKeyboard() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + K 聚焦搜索
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            elements.searchInput.focus();
        }
        
        // Escape 关闭搜索或侧边栏
        if (e.key === 'Escape') {
            if (document.activeElement === elements.searchInput) {
                elements.searchInput.blur();
                elements.searchInput.value = '';
                performSearch('');
            }
            if (window.innerWidth <= 768) {
                closeSidebar();
            }
        }
    });
}

// 初始化应用
function init() {
    initMarked();
    initChapterList();
    initSearch();
    initTheme();
    initSidebar();
    initBackToTop();
    initKeyboard();
    loadFromHash();
}

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', init);