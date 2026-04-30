/**
 * 全页面统一的主题管理器
 * 提供一致的主题切换体验，所有页面共享同一个主题状态
 */

class ThemeManager {
    constructor() {
        this.themeToggle = null;
        this.themeIcon = null;
        this.init();
    }

    init() {
        // 获取主题切换按钮（优先导航栏按钮，兼容旧版右下角浮动按钮）
        this.themeToggle = document.getElementById('themeToggleNav') || document.getElementById('themeToggle');
        if (!this.themeToggle) {
            console.warn('主题切换按钮未找到，将在页面加载后重试');
            setTimeout(() => this.init(), 100);
            return;
        }

        this.themeIcon = this.themeToggle.querySelector('i');
        
        // 初始化主题
        this.initTheme();
        
        // 绑定事件
        this.bindEvents();
    }

    initTheme() {
        // 从localStorage获取主题，默认使用暗黑模式
        const savedTheme = localStorage.getItem('theme');
        let theme;
        
        if (savedTheme) {
            theme = savedTheme;
        } else {
            // 如果没有保存的主题，使用暗黑模式作为默认
            theme = 'dark';
            localStorage.setItem('theme', theme);
        }
        
        // 应用主题
        this.applyTheme(theme);
        
        // 更新图标
        this.updateThemeIcon(theme);
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-bs-theme', theme);
        
        // 触发主题变化事件，供其他组件监听
        const event = new CustomEvent('themeChanged', { detail: { theme } });
        document.dispatchEvent(event);
    }

    updateThemeIcon(theme) {
        if (!this.themeIcon) return;
        
        if (theme === 'dark') {
            this.themeIcon.className = 'bi bi-sun';
            this.themeToggle.title = '切换到亮色模式';
        } else {
            this.themeIcon.className = 'bi bi-moon-stars';
            this.themeToggle.title = '切换到暗黑模式';
        }
    }

    bindEvents() {
        this.themeToggle.addEventListener('click', () => {
            this.toggleTheme();
        });
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        // 应用新主题
        this.applyTheme(newTheme);
        
        // 保存到localStorage
        localStorage.setItem('theme', newTheme);
        
        // 更新图标
        this.updateThemeIcon(newTheme);
        
        // 添加切换动画
        this.themeToggle.classList.add('animate__animated', 'animate__flip');
        setTimeout(() => {
            this.themeToggle.classList.remove('animate__animated', 'animate__flip');
        }, 500);
    }

    getCurrentTheme() {
        return document.documentElement.getAttribute('data-bs-theme') || 'dark';
    }

    isDarkMode() {
        return this.getCurrentTheme() === 'dark';
    }

    isLightMode() {
        return this.getCurrentTheme() === 'light';
    }

    // 静态方法，用于快速获取主题状态
    static getTheme() {
        return localStorage.getItem('theme') || 'dark';
    }

    static isDark() {
        return ThemeManager.getTheme() === 'dark';
    }

    static isLight() {
        return ThemeManager.getTheme() === 'light';
    }
}

// 自动初始化主题管理器
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
    
    // 监听主题变化事件
    document.addEventListener('themeChanged', (event) => {
        console.log(`主题已切换为: ${event.detail.theme}`);
        
        // 这里可以添加其他需要在主题变化时执行的逻辑
        // 例如：更新图表颜色、调整组件样式等
    });
});

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}