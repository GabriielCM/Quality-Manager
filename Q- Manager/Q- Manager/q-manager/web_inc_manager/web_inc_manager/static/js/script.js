/**
 * Q-Manager - Main JavaScript
 * Version: 1.0.0
 * Contém todas as funcionalidades JavaScript do sistema
 */

// ===== CONFIGURAÇÕES GLOBAIS =====
const CONFIG = {
    TOAST_TIMEOUT: 5000,         // Tempo para fechar os toasts automaticamente (ms)
    NOTIFICATION_CHECK: 60000,   // Intervalo para verificar novas notificações (ms)
    ANIMATION_SPEED: 300,        // Velocidade das animações (ms)
    DEBOUNCE_TIMEOUT: 300,       // Timeout para funções debounce (ms)
    THEME_SETTINGS: {
        default: {
            primary: '#3498db',
            secondary: '#2c3e50',
            success: '#2ecc71',
            info: '#3498db',
            warning: '#f39c12',
            danger: '#e74c3c'
        },
        emerald: {
            primary: '#2ecc71',
            secondary: '#27ae60',
            success: '#27ae60',
            info: '#3498db',
            warning: '#f39c12',
            danger: '#e74c3c'
        },
        sunset: {
            primary: '#e74c3c',
            secondary: '#c0392b',
            success: '#2ecc71',
            info: '#f39c12',
            warning: '#f39c12',
            danger: '#e74c3c'
        },
        lavender: {
            primary: '#9b59b6',
            secondary: '#8e44ad',
            success: '#2ecc71',
            info: '#3498db',
            warning: '#f39c12',
            danger: '#e74c3c'
        },
        ocean: {
            primary: '#1abc9c',
            secondary: '#16a085',
            success: '#2ecc71',
            info: '#3498db',
            warning: '#f39c12',
            danger: '#e74c3c'
        }
    }
};

// ===== UTILITÁRIOS =====

/**
 * Função debounce para evitar múltiplas chamadas de funções
 * @param {Function} func - A função a ser executada
 * @param {number} wait - Tempo de espera em milissegundos
 * @return {Function} - Função com debounce
 */
function debounce(func, wait = CONFIG.DEBOUNCE_TIMEOUT) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

/**
 * Formatador de datas para visualização amigável
 * @param {string} dateString - String de data no formato ISO ou DD-MM-YYYY
 * @return {string} - Data formatada 
 */
function formatDate(dateString) {
    if (!dateString) return '';
    
    // Verifica se está no formato DD-MM-YYYY
    if (/^\d{2}-\d{2}-\d{4}$/.test(dateString)) {
        const [day, month, year] = dateString.split('-');
        return `${day}/${month}/${year}`;
    }
    
    // Verifica se está no formato YYYY-MM-DD
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
        const [year, month, day] = dateString.split('-');
        return `${day}/${month}/${year}`;
    }
    
    return dateString;
}

/**
 * Formata número como moeda em Reais
 * @param {number} value - O valor a ser formatado
 * @return {string} - Valor formatado como moeda
 */
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

// ===== FUNÇÕES PARA MANIPULAÇÃO DE CRM =====

/**
 * Abre o link do CRM para o item especificado
 * @param {string} item - Código do item a ser consultado
 * @param {string} token - Token de autenticação do CRM
 */
function openCRMLink(item, token) {
    if (!token) {
        showToast('Token CRM não disponível', 'danger');
        return;
    }
    
    const baseUrlElement = document.getElementById('crm-base-url');
    if (!baseUrlElement) {
        showToast('Configuração do CRM não disponível', 'danger');
        return;
    }
    
    const baseUrl = baseUrlElement.dataset.url;
    const encodedItem = encodeURIComponent(item);
    const link = `${baseUrl}&token=${token}&cod_item=${encodedItem}&filter_cod=${item.toLowerCase()}`;
    window.open(link, '_blank');
}

// ===== FUNÇÕES PARA A ROTINA DE INSPEÇÃO =====

/**
 * Salva a posição de rolagem atual
 * @return {number} - Posição atual do scroll
 */
function saveScrollPosition() {
    const scrollPosition = window.scrollY || window.pageYOffset;
    
    // Armazena em localStorage para persistência entre requisições
    localStorage.setItem('inspecao_scroll_position', scrollPosition);
    
    // Atualiza todos os campos de posição de rolagem na página
    document.querySelectorAll('input[name="scroll_position"]').forEach(input => {
        input.value = scrollPosition;
    });
    
    return scrollPosition;
}

/**
 * Função para salvar a posição e submeter o formulário
 * @param {HTMLFormElement} form - Formulário a ser submetido
 * @param {string} action - Ação realizada ('inspecionar' ou 'adiar')
 * @param {number} ar - Número do AR
 * @param {number} index - Índice do item na lista
 * @return {boolean} - Sempre retorna true para permitir o submit
 */
function saveAndSubmit(form, action, ar, index) {
    // Salva a posição de rolagem atual
    const scrollPosition = window.scrollY || window.pageYOffset;
    
    // Armazena em localStorage para persistência entre requisições
    localStorage.setItem('inspecao_scroll_position', scrollPosition);
    
    // Atualiza o campo hidden no formulário
    form.querySelector('.scroll-position-input').value = scrollPosition;
    
    // Permite que o formulário seja enviado
    return true;
}

/**
 * Restaura a posição de rolagem após recarregar a página
 */
function restoreScrollPosition() {
    // Tenta obter do localStorage primeiro (mais confiável)
    let scrollPosition = localStorage.getItem('inspecao_scroll_position');
    
    // Se não estiver no localStorage, tenta obter do campo hidden ou da URL
    if (!scrollPosition) {
        const storedElement = document.getElementById('stored_scroll_position');
        if (storedElement) {
            scrollPosition = storedElement.value;
        }
    }
    
    // Se encontrou uma posição, rola para ela com um pequeno atraso para garantir
    // que todos os elementos da página estejam carregados
    if (scrollPosition && scrollPosition !== '0') {
        setTimeout(() => {
            window.scrollTo({
                top: parseInt(scrollPosition),
                behavior: 'auto' // Usa 'auto' em vez de 'smooth' para evitar animação visível
            });
        }, 100);
    }
}

/**
 * Atualiza o estado do botão de salvar na rotina de inspeção
 */
function updateSaveButton() {
    const statusCells = document.querySelectorAll('.status-cell');
    let allProcessed = true;
    let totalProcessed = 0;
    let total = statusCells.length;
    
    statusCells.forEach(cell => {
        const inspecionado = cell.getAttribute('data-inspecionado') === 'true';
        const adiado = cell.getAttribute('data-adiado') === 'true';
        if (!inspecionado && !adiado) {
            allProcessed = false;
        } else {
            totalProcessed++;
        }
    });
    
    const saveButton = document.getElementById('saveButton');
    if (saveButton) {
        saveButton.disabled = !allProcessed;
        
        // Adiciona um contador de progresso
        if (total > 0) {
            const progressPercent = Math.round((totalProcessed / total) * 100);
            const progressBadge = document.createElement('span');
            progressBadge.className = 'badge bg-info ms-2';
            progressBadge.textContent = `${progressPercent}% (${totalProcessed}/${total})`;
            
            // Remove badge anterior se existir
            const existingBadge = saveButton.querySelector('.badge');
            if (existingBadge) {
                existingBadge.remove();
            }
            
            // Adiciona nova badge apenas se não estiver 100% completo
            if (progressPercent < 100) {
                saveButton.appendChild(progressBadge);
            }
        }
    }
}

// ===== TOGGLE DA SIDEBAR =====

/**
 * Alterna a visibilidade da barra lateral
 */
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('active');
}

// ===== NOTIFICAÇÕES TOAST =====

/**
 * Exibe uma mensagem toast
 * @param {string} message - Mensagem a ser exibida
 * @param {string} type - Tipo de mensagem (success, info, warning, danger)
 */
function showToast(message, type = 'info') {
    // Verifica se o container existe
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '1100';
        document.body.appendChild(toastContainer);
    }
    
    // Gera um ID único para o toast
    const toastId = 'toast-' + Date.now();
    
    // Determina o ícone com base no tipo
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'warning') icon = 'exclamation-triangle';
    if (type === 'danger') icon = 'exclamation-circle';
    
    // Cria o HTML do toast
    const toast = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${icon} me-2"></i> ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    // Adiciona o toast ao container
    toastContainer.innerHTML += toast;
    
    // Inicializa e mostra o toast usando o Bootstrap
    const toastElement = document.getElementById(toastId);
    if (typeof bootstrap !== 'undefined') {
        const bsToast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: CONFIG.TOAST_TIMEOUT
        });
        bsToast.show();
    } else {
        // Fallback para navegadores sem Bootstrap
        toastElement.style.display = 'block';
        setTimeout(() => {
            toastElement.remove();
        }, CONFIG.TOAST_TIMEOUT);
    }
    
    // Remove automaticamente após exibição
    toastElement.addEventListener('hidden.bs.toast', function () {
        toastElement.remove();
    });
}

// ===== ANIMAÇÕES E EFEITOS VISUAIS =====

/**
 * Adiciona efeitos de hover em diversos elementos
 */
function addHoverEffects() {
    // Efeito de hover em imagens
    document.querySelectorAll('.image-container img').forEach(img => {
        img.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.05)';
            this.style.transition = 'transform 0.3s ease';
            this.style.zIndex = '1';
            this.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)';
        });
        
        img.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
            this.style.zIndex = '0';
            this.style.boxShadow = 'none';
        });
    });
    
    // Efeito de hover em cards
    document.querySelectorAll('.card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.boxShadow = '0 8px 16px rgba(0,0,0,0.1)';
            this.style.transition = 'box-shadow 0.3s ease';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
        });
    });
}

// ===== VALIDAÇÕES DE FORMULÁRIOS =====

/**
 * Valida intervalo de datas para formulários com data inicial e final
 * @param {HTMLElement} startEl - Elemento de data inicial
 * @param {HTMLElement} endEl - Elemento de data final
 */
function validateDateRange(startEl, endEl) {
    if (!startEl || !endEl) return;
    
    endEl.addEventListener('change', function() {
        if (startEl.value && endEl.value) {
            if (new Date(endEl.value) < new Date(startEl.value)) {
                showToast('A data final não pode ser menor que a data inicial!', 'danger');
                endEl.value = '';
            }
        }
    });
}

// ===== SISTEMA DE NOTIFICAÇÕES =====

/**
 * Classe para gerenciar o sistema de notificações
 */
class NotificationSystem {
    constructor() {
        this.container = document.getElementById('notification-center');
        this.button = document.getElementById('notificationButton');
        this.badge = document.querySelector('.notification-badge');
        this.list = document.querySelector('.notification-list');
        this.markAllReadButton = document.getElementById('mark-all-read');
        this.notifications = [];
        
        this.init();
    }
    
    init() {
        if (!this.container || !this.button) return;
        
        // Configurar evento de clique no botão de notificações
        this.button.addEventListener('click', () => {
            this.toggleNotificationCenter();
        });
        
        // Configurar botão de marcar todas como lidas
        if (this.markAllReadButton) {
            this.markAllReadButton.addEventListener('click', () => {
                this.markAllAsRead();
            });
        }
        
        // Iniciar verificação de notificações
        this.checkNotifications();
        setInterval(() => this.checkNotifications(), CONFIG.NOTIFICATION_CHECK);
    }
    
    toggleNotificationCenter() {
        this.container.classList.toggle('open');
    }
    
    async checkNotifications() {
        try {
            // Na implementação real, isso faria uma chamada AJAX para o servidor
            // Para fins de demonstração, usaremos notificações simuladas
            this.mockNotifications();
        } catch (error) {
            console.error('Erro ao verificar notificações:', error);
        }
    }
    
    mockNotifications() {
        // Adicionar algumas notificações de exemplo para demonstração
        const today = new Date();
        
        // Limpar notificações existentes para demonstração
        this.notifications = [];
        
        // Adicionar notificações de exemplo
        this.addNotification({
            id: 1,
            type: 'warning',
            title: 'INCs próximas ao vencimento',
            message: 'Você tem 3 INCs que vencem em 2 dias',
            time: today.toISOString(),
            read: false,
            link: '/expiracao_inc'
        });
        
        this.addNotification({
            id: 2,
            type: 'info',
            title: 'Nova rotina de inspeção',
            message: 'Uma nova rotina de inspeção foi adicionada',
            time: new Date(today.getTime() - 3600000).toISOString(), // 1 hora atrás
            read: true,
            link: '/rotina_inspecao'
        });
        
        this.addNotification({
            id: 3,
            type: 'success',
            title: 'INC #123 concluída',
            message: 'A INC #123 foi marcada como concluída',
            time: new Date(today.getTime() - 86400000).toISOString(), // 1 dia atrás
            read: false,
            link: '/detalhes_inc/123'
        });
    }
    
    addNotification(notification) {
        // Verifica se a notificação já existe
        const existingIndex = this.notifications.findIndex(n => n.id === notification.id);
        if (existingIndex >= 0) {
            this.notifications[existingIndex] = notification;
        } else {
            this.notifications.push(notification);
        }
        
        // Atualiza a interface
        this.render();
    }
    
    markAsRead(id) {
        const notification = this.notifications.find(n => n.id === id);
        if (notification) {
            notification.read = true;
            
            // Na implementação real, isso enviaria uma requisição para o servidor
            // para marcar a notificação como lida no banco de dados
            
            this.render();
        }
    }
    
    markAllAsRead() {
        this.notifications.forEach(notification => {
            notification.read = true;
        });
        
        // Na implementação real, isso enviaria uma requisição para o servidor
        // para marcar todas as notificações como lidas no banco de dados
        
        this.render();
    }
    
    render() {
        // Atualizar contador de notificações não lidas
        const unreadCount = this.notifications.filter(n => !n.read).length;
        
        if (this.badge) {
            this.badge.textContent = unreadCount;
            this.badge.style.display = unreadCount > 0 ? 'block' : 'none';
        }
        
        // Atualizar lista de notificações
        if (this.list) {
            if (this.notifications.length === 0) {
                this.list.innerHTML = '<div class="notification-empty">Sem notificações</div>';
            } else {
                this.list.innerHTML = this.notifications
                    .sort((a, b) => new Date(b.time) - new Date(a.time)) // Ordenar por mais recente
                    .map(notification => this.renderNotification(notification))
                    .join('');
                
                // Adicionar event listeners nos itens
                this.list.querySelectorAll('.notification-item').forEach(item => {
                    const id = parseInt(item.dataset.id);
                    
                    // Marcar como lida ao clicar no botão de fechar
                    item.querySelector('.notification-close')?.addEventListener('click', e => {
                        e.preventDefault();
                        e.stopPropagation();
                        this.markAsRead(id);
                    });
                    
                    // Navegar para o link ao clicar no item
                    item.addEventListener('click', () => {
                        const notification = this.notifications.find(n => n.id === id);
                        if (notification && notification.link) {
                            this.markAsRead(id);
                            window.location.href = notification.link;
                        }
                    });
                });
            }
        }
    }
    
    renderNotification(notification) {
        const date = new Date(notification.time);
        const timeStr = date.toLocaleString();
        
        return `
            <div class="notification-item ${notification.read ? 'read' : 'unread'}" data-id="${notification.id}">
                <div class="notification-icon">
                    <i class="fas fa-${notification.type === 'warning' ? 'exclamation-triangle' : 
                                      notification.type === 'success' ? 'check-circle' : 'info-circle'} 
                             text-${notification.type}"></i>
                </div>
                <div class="notification-content">
                    <div class="notification-title">${notification.title}</div>
                    <div class="notification-message">${notification.message}</div>
                    <div class="notification-time">${timeStr}</div>
                </div>
                <div class="notification-close">
                    <i class="fas fa-times"></i>
                </div>
            </div>
        `;
    }
}

// ===== SISTEMA DE TEMAS =====

/**
 * Classe para gerenciar o sistema de temas
 */
class ThemeSystem {
    constructor() {
        this.toggleButton = document.getElementById('theme-toggle');
        this.panel = document.querySelector('.theme-panel');
        this.themeOptions = document.querySelectorAll('.theme-option');
        this.darkModeSwitch = document.getElementById('darkModeSwitch');
        this.fontSelector = document.getElementById('fontSelector');
        this.nightModeButton = document.getElementById('toggleNightMode');
        
        this.init();
    }
    
    init() {
        // Carregar tema salvo
        this.loadSavedTheme();
        
        // Toggle do painel de temas
        if (this.toggleButton && this.panel) {
            this.toggleButton.addEventListener('click', () => {
                this.panel.classList.toggle('open');
            });
            
            // Fechar painel ao clicar fora
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.theme-selector') && this.panel.classList.contains('open')) {
                    this.panel.classList.remove('open');
                }
            });
        }
        
        // Mudar tema
        if (this.themeOptions) {
            this.themeOptions.forEach(option => {
                option.addEventListener('click', () => {
                    const theme = option.dataset.theme;
                    this.setTheme(theme);
                    
                    // Atualizar seleção visual
                    this.themeOptions.forEach(op => op.classList.remove('active'));
                    option.classList.add('active');
                });
            });
        }
        
        // Toggle do modo escuro via switch
        if (this.darkModeSwitch) {
            this.darkModeSwitch.addEventListener('change', () => {
                this.toggleDarkMode(this.darkModeSwitch.checked);
            });
        }
        
        // Toggle do modo escuro via botão no rodapé
        if (this.nightModeButton) {
            this.nightModeButton.addEventListener('click', () => {
                const isDarkMode = document.body.classList.contains('night-mode');
                this.toggleDarkMode(!isDarkMode);
                
                // Atualizar switch se existir
                if (this.darkModeSwitch) {
                    this.darkModeSwitch.checked = !isDarkMode;
                }
            });
        }
        
        // Mudar fonte
        if (this.fontSelector) {
            this.fontSelector.addEventListener('change', () => {
                this.setFont(this.fontSelector.value);
            });
        }
    }
    
    loadSavedTheme() {
        // Carregar tema do localStorage
        const savedTheme = localStorage.getItem('theme') || 'default';
        const isDarkMode = localStorage.getItem('nightMode') === 'true';
        const savedFont = localStorage.getItem('font') || "'Segoe UI', sans-serif";
        
        // Aplicar tema
        this.setTheme(savedTheme, false);
        
        // Marcar a opção ativa
        if (this.themeOptions) {
            this.themeOptions.forEach(option => {
                if (option.dataset.theme === savedTheme) {
                    option.classList.add('active');
                }
            });
        }
        
        // Aplicar modo escuro
        this.toggleDarkMode(isDarkMode, false);
        
        // Atualizar checkbox
        if (this.darkModeSwitch) {
            this.darkModeSwitch.checked = isDarkMode;
        }
        
        // Aplicar fonte
        this.setFont(savedFont, false);
        if (this.fontSelector) {
            this.fontSelector.value = savedFont;
        }
    }
    
    setTheme(theme, save = true) {
        // Remove classes de tema anteriores
        document.body.classList.forEach(cls => {
            if (cls.startsWith('theme-')) {
                document.body.classList.remove(cls);
            }
        });
        
        // Adiciona a nova classe de tema
        document.body.classList.add(`theme-${theme}`);
        
        // Aplicar variáveis CSS do tema
        const themeColors = CONFIG.THEME_SETTINGS[theme] || CONFIG.THEME_SETTINGS.default;
        for (const [key, value] of Object.entries(themeColors)) {
            document.documentElement.style.setProperty(`--${key}-color`, value);
        }
        
        // Salva a preferência
        if (save) {
            localStorage.setItem('theme', theme);
        }
    }
    
    toggleDarkMode(enable, save = true) {
        if (enable) {
            document.body.classList.add('night-mode');
            
            // Atualizar ícone no botão de toggle
            if (this.nightModeButton) {
                const icon = this.nightModeButton.querySelector('i');
                if (icon) {
                    icon.className = 'fas fa-sun';
                }
                
                // Atualizar estilo do botão
                this.nightModeButton.classList.remove('btn-outline-light');
                this.nightModeButton.classList.add('btn-outline-warning');
            }
            
            // Atualizar estilo do rodapé
            const footer = document.querySelector('.footer');
            if (footer) {
                footer.style.backgroundColor = '#1a2530';
            }
        } else {
            document.body.classList.remove('night-mode');
            
            // Atualizar ícone no botão de toggle
            if (this.nightModeButton) {
                const icon = this.nightModeButton.querySelector('i');
                if (icon) {
                    icon.className = 'fas fa-moon';
                }
                
                // Atualizar estilo do botão
                this.nightModeButton.classList.remove('btn-outline-warning');
                this.nightModeButton.classList.add('btn-outline-light');
            }
            
            // Atualizar estilo do rodapé
            const footer = document.querySelector('.footer');
            if (footer) {
                footer.style.backgroundColor = '';
            }
        }
        
        // Salvar preferência
        if (save) {
            localStorage.setItem('nightMode', enable);
        }
        
        // Disparar evento personalizado para que os gráficos possam atualizar
        const event = new CustomEvent('themeChanged', { detail: { darkMode: enable } });
        document.dispatchEvent(event);
    }
    
    setFont(fontFamily, save = true) {
        document.documentElement.style.setProperty('--font-family', fontFamily);
        
        if (save) {
            localStorage.setItem('font', fontFamily);
        }
    }
}

// ===== SISTEMA DE ETIQUETAS =====

/**
 * Classe para gerenciar o sistema de etiquetas
 */
class TagSystem {
    constructor(container) {
        if (!container) return;
        
        this.container = container;
        this.selectedTags = new Set();
        this.init();
    }
    
    init() {
        const input = this.container.querySelector('.tag-input');
        const suggestions = this.container.querySelector('.tag-suggestions');
        const selectedTagsContainer = this.container.querySelector('.selected-tags');
        const hiddenInput = document.getElementById('tags-input');
        
        if (!input || !suggestions || !selectedTagsContainer) return;
        
        // Carrega as tags já selecionadas
        if (hiddenInput && hiddenInput.value) {
            this.selectedTags = new Set(hiddenInput.value.split(','));
        }
        
        // Event listeners
        input.addEventListener('focus', () => {
            suggestions.style.display = 'block';
        });
        
        input.addEventListener('blur', (e) => {
            // Atraso para permitir cliques nos itens da sugestão
            setTimeout(() => {
                suggestions.style.display = 'none';
            }, 200);
        });
        
        input.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            this.filterSuggestions(query);
        });
        
        // Lidar com sugestões
        const suggestionItems = this.container.querySelectorAll('.tag-suggestion:not(.create-tag)');
        suggestionItems.forEach(item => {
            item.addEventListener('click', () => {
                const tagId = item.dataset.tagId;
                const tagName = item.dataset.tagName;
                const tagColor = item.dataset.tagColor;
                
                if (!this.selectedTags.has(tagId)) {
                    this.addTag(tagId, tagName, tagColor);
                }
                
                input.value = '';
                suggestions.style.display = 'none';
            });
        });
        
        // Criar nova etiqueta
        const createTagButton = this.container.querySelector('.create-tag');
        if (createTagButton) {
            createTagButton.addEventListener('click', () => {
                this.openTagCreationModal(input.value);
                input.value = '';
                suggestions.style.display = 'none';
            });
        }
        
        // Remover tags
        selectedTagsContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('tag-remove')) {
                const tagId = e.target.dataset.tagId;
                this.removeTag(tagId);
            }
        });
    }
    
    filterSuggestions(query) {
        const createTagText = document.getElementById('create-tag-text');
        const suggestionItems = this.container.querySelectorAll('.tag-suggestion:not(.create-tag)');
        
        if (createTagText) {
            createTagText.textContent = query ? `Criar etiqueta "${query}"` : 'Criar nova etiqueta';
        }
        
        suggestionItems.forEach(item => {
            const tagName = item.dataset.tagName.toLowerCase();
            const match = tagName.includes(query);
            const isSelected = this.selectedTags.has(item.dataset.tagId);
            
            item.style.display = !match || isSelected ? 'none' : 'flex';
        });
    }
    
    addTag(id, name, color) {
        this.selectedTags.add(id);
        this.updateHiddenInput();
        this.updateTagsDisplay();
        
        // Adiciona visualmente
        const selectedTagsContainer = this.container.querySelector('.selected-tags');
        const tagElement = document.createElement('span');
        tagElement.className = 'tag';
        tagElement.dataset.tagId = id;
        tagElement.style.backgroundColor = color;
        tagElement.innerHTML = `
            ${name}
            <i class="fas fa-times tag-remove" data-tag-id="${id}"></i>
        `;
        
        selectedTagsContainer.appendChild(tagElement);
    }
    
    removeTag(id) {
        this.selectedTags.delete(id);
        this.updateHiddenInput();
        
        // Remove visualmente
        const tagElement = this.container.querySelector(`.tag[data-tag-id="${id}"]`);
        if (tagElement) {
            tagElement.remove();
        }
    }
    
    updateHiddenInput() {
        const hiddenInput = document.getElementById('tags-input');
        if (hiddenInput) {
            hiddenInput.value = Array.from(this.selectedTags).join(',');
        }
    }
    
    updateTagsDisplay() {
        const suggestions = this.container.querySelectorAll('.tag-suggestion:not(.create-tag)');
        suggestions.forEach(item => {
            const tagId = item.dataset.tagId;
            item.style.display = this.selectedTags.has(tagId) ? 'none' : 'flex';
        });
    }
    
    openTagCreationModal(tagName) {
        // Criar modal para definição de nova etiqueta
        const modalHTML = `
            <div class="modal fade" id="createTagModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Criar Nova Etiqueta</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label">Nome da Etiqueta</label>
                                <input type="text" class="form-control" id="new-tag-name" value="${tagName || ''}">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Cor</label>
                                <div class="color-picker">
                                    <div class="color-option" data-color="#3498db" style="background-color: #3498db;"></div>
                                    <div class="color-option" data-color="#2ecc71" style="background-color: #2ecc71;"></div>
                                    <div class="color-option" data-color="#e74c3c" style="background-color: #e74c3c;"></div>
                                    <div class="color-option" data-color="#f39c12" style="background-color: #f39c12;"></div>
                                    <div class="color-option" data-color="#9b59b6" style="background-color: #9b59b6;"></div>
                                    <div class="color-option" data-color="#34495e" style="background-color: #34495e;"></div>
                                    <div class="color-option" data-color="#1abc9c" style="background-color: #1abc9c;"></div>
                                    <div class="color-option" data-color="#e67e22" style="background-color: #e67e22;"></div>
                                </div>
                                <input type="hidden" id="new-tag-color" value="#3498db">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                            <button type="button" class="btn btn-primary" id="save-new-tag">Salvar Etiqueta</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Adiciona o modal ao documento se não existir
        if (!document.getElementById('createTagModal')) {
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHTML;
            document.body.appendChild(modalContainer);
            
            // Configura os event listeners do modal
            const colorOptions = document.querySelectorAll('.color-option');
            colorOptions.forEach(option => {
                option.addEventListener('click', () => {
                    // Remove seleção anterior
                    colorOptions.forEach(op => op.classList.remove('selected'));
                    
                    // Seleciona a nova cor
                    option.classList.add('selected');
                    document.getElementById('new-tag-color').value = option.dataset.color;
                });
                
                // Seleciona a primeira cor por padrão
                if (option.dataset.color === '#3498db') {
                    option.classList.add('selected');
                }
            });
            
            // Salvar nova etiqueta
            document.getElementById('save-new-tag').addEventListener('click', () => {
                const name = document.getElementById('new-tag-name').value;
                const color = document.getElementById('new-tag-color').value;
                
                if (name) {
                    this.saveNewTag(name, color);
                    if (typeof bootstrap !== 'undefined') {
                        const modal = bootstrap.Modal.getInstance(document.getElementById('createTagModal'));
                        if (modal) modal.hide();
                    }
                }
            });
        }
        
        // Exibe o modal
        if (typeof bootstrap !== 'undefined') {
            const modal = new bootstrap.Modal(document.getElementById('createTagModal'));
            modal.show();
        }
    }
    
    saveNewTag(name, color) {
        // Na implementação real, isso faria uma chamada AJAX para salvar a tag no servidor
        // Para demonstração, simulamos o retorno com um novo ID
        const newTagId = 'tag_' + Date.now();
        
        // Simula resposta do servidor
        const data = {
            success: true,
            tag: {
                id: newTagId,
                name: name,
                color: color
            }
        };
        
        if (data.success) {
            // Adiciona a nova tag à lista de sugestões
            const suggestions = this.container.querySelector('.tag-suggestions');
            const createTagElement = suggestions.querySelector('.create-tag');
            
            const newSuggestion = document.createElement('div');
            newSuggestion.className = 'tag-suggestion';
            newSuggestion.dataset.tagId = data.tag.id;
            newSuggestion.dataset.tagName = data.tag.name;
            newSuggestion.dataset.tagColor = data.tag.color;
            newSuggestion.innerHTML = `
                <span class="tag-color" style="background-color: ${data.tag.color}"></span>
                <span class="tag-name">${data.tag.name}</span>
            `;
            
            // Adiciona antes do elemento "criar tag"
            if (createTagElement) {
                suggestions.insertBefore(newSuggestion, createTagElement);
            } else {
                suggestions.appendChild(newSuggestion);
            }
            
            // Adiciona event listener
            newSuggestion.addEventListener('click', () => {
                this.addTag(data.tag.id, data.tag.name, data.tag.color);
            });
            
            // Adiciona a tag ao selecionados
            this.addTag(data.tag.id, data.tag.name, data.tag.color);
            
            showToast(`Etiqueta "${data.tag.name}" criada com sucesso`, 'success');
        } else {
            showToast(`Erro ao criar etiqueta`, 'danger');
        }
    }
}

// ===== KANBAN DRAG AND DROP =====

/**
 * Classe para gerenciar o sistema Kanban de arrastar e soltar
 */
class KanbanManager {
    constructor() {
        this.items = document.querySelectorAll('.kanban-item');
        this.columns = document.querySelectorAll('.kanban-items');
        this.draggedItem = null;
        
        if (this.items.length > 0 && this.columns.length > 0) {
            this.init();
        }
    }
    
    init() {
        // Configurar itens arrastáveis
        this.items.forEach(item => {
            item.addEventListener('dragstart', () => {
                this.draggedItem = item;
                setTimeout(() => item.classList.add('dragging'), 0);
            });
            
            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
                this.draggedItem = null;
            });
        });
        
        // Configurar colunas para receber itens
        this.columns.forEach(column => {
            column.addEventListener('dragover', e => {
                e.preventDefault();
                column.classList.add('drag-over');
            });
            
            column.addEventListener('dragleave', () => {
                column.classList.remove('drag-over');
            });
            
            column.addEventListener('drop', e => {
                e.preventDefault();
                column.classList.remove('drag-over');
                
                if (this.draggedItem) {
                    // Identificar a coluna de destino
                    const newStatus = column.closest('.kanban-column').querySelector('.kanban-column-header h5').textContent.trim();
                    const incId = this.draggedItem.dataset.id;
                    
                    // Atualizar o status da INC (chamada à API)
                    this.updateIncStatus(incId, newStatus);
                    
                    // Mover o item visualmente
                    column.appendChild(this.draggedItem);
                    
                    // Atualizar contadores
                    this.updateCounters();
                }
            });
        });
    }
    
    updateCounters() {
        // Atualizar contadores de cada coluna
        this.columns.forEach(column => {
            const header = column.closest('.kanban-column').querySelector('.kanban-column-header');
            const counter = header.querySelector('.badge');
            const count = column.querySelectorAll('.kanban-item').length;
            
            if (counter) {
                counter.textContent = count;
            }
        });
    }
    
    updateIncStatus(incId, newStatus) {
        // Mapeia o título da coluna para o valor do status no banco
        const statusMap = {
            'Em andamento': 'Em andamento',
            'Aguardando Fornecedor': 'Aguardando',
            'Concluídas': 'Concluída'
        };
        
        const status = statusMap[newStatus] || newStatus;
        
        // Na implementação real, isso faria uma chamada AJAX para atualizar o status no servidor
        // Simular atualização bem-sucedida
        showToast(`INC #${incId} movida para "${status}"`, 'success');
        
        // Atualizar a aparência do card
        const card = document.querySelector(`.kanban-item[data-id="${incId}"]`);
        if (card) {
            const statusBadge = card.querySelector('.status-badge');
            if (statusBadge) {
                // Remover classes de cor anteriores
                statusBadge.classList.remove('bg-primary', 'bg-success', 'bg-danger', 'bg-warning');
                
                // Adicionar nova classe de cor
                if (status === 'Em andamento') {
                    statusBadge.classList.add('bg-primary');
                } else if (status === 'Concluída') {
                    statusBadge.classList.add('bg-success');
                } else if (status === 'Aguardando') {
                    statusBadge.classList.add('bg-warning');
                } else {
                    statusBadge.classList.add('bg-secondary');
                }
                
                // Atualizar texto
                statusBadge.textContent = status;
            }
        }
    }
}

// ===== FUNÇÕES DE GRÁFICOS E VISUALIZAÇÕES =====

/**
 * Atualiza a aparência dos gráficos Chart.js para modo escuro/claro
 * @param {boolean} isDarkMode - Se o modo escuro está ativado
 */
function updateChartsTheme(isDarkMode) {
    if (typeof Chart === 'undefined') return;
    
    // Configurações globais para Chart.js
    Chart.defaults.color = isDarkMode ? '#ecf0f1' : '#666';
    Chart.defaults.borderColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    
    // Atualizar todos os gráficos na página
    Chart.instances.forEach(chart => {
        chart.update();
    });
}

// ===== INICIALIZAÇÃO QUANDO O DOCUMENTO ESTIVER PRONTO =====

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar sistema de temas
    const themeSystem = new ThemeSystem();
    
    // Inicializar sistema de notificações
    const notificationSystem = new NotificationSystem();
    
    // Toggle da sidebar
    const sidebarCollapse = document.getElementById('sidebarCollapse');
    if (sidebarCollapse) {
        sidebarCollapse.addEventListener('click', toggleSidebar);
    }
    
    // Preencher todos os inputs de posição de rolagem com o valor atual
    document.querySelectorAll('.scroll-position-input').forEach(input => {
        input.value = window.scrollY || window.pageYOffset;
    });
    
    // Restaurar a posição de rolagem em páginas relevantes
    if (document.getElementById('stored_scroll_position')) {
        restoreScrollPosition();
    }
    
    // Formatadores de dados
    document.querySelectorAll('.format-date').forEach(function(element) {
        const date = element.textContent.trim();
        if (date) {
            element.title = formatDate(date);
        }
    });
    
    // Inicializar tooltips Bootstrap, se disponível
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Verificar botões de salvar para rotinas de inspeção
    updateSaveButton();
    
    // Auto-esconder alertas após 5 segundos
    document.querySelectorAll('.alert:not(.alert-permanent)').forEach(function(alert) {
        setTimeout(function() {
            const closeButton = alert.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            }
        }, CONFIG.TOAST_TIMEOUT);
    });
    
    // Adicionar efeitos visuais
    addHoverEffects();
    
    // Validação de campos de data
    const startDateField = document.getElementById('start_date');
    const endDateField = document.getElementById('end_date');
    if (startDateField && endDateField) {
        validateDateRange(startDateField, endDateField);
    }
    
    // Destacar visualmente os status nas tabelas de inspeção
    document.querySelectorAll('.status-cell').forEach(cell => {
        const inspecionado = cell.getAttribute('data-inspecionado') === 'true';
        const adiado = cell.getAttribute('data-adiado') === 'true';
        
        if (inspecionado) {
            cell.parentElement.classList.add('table-success');
        } else if (adiado) {
            cell.parentElement.classList.add('table-warning');
        }
    });
    
    // Inicializar sistema de etiquetas
    const tagContainer = document.querySelector('.tag-input-container');
    if (tagContainer) {
        const tagSystem = new TagSystem(tagContainer);
    }
    
    // Inicializar sistema de kanban
    const kanbanContainer = document.querySelector('.kanban-container');
    if (kanbanContainer) {
        const kanbanManager = new KanbanManager();
    }
    
    // Eventos para atualização de temas em gráficos
    document.addEventListener('themeChanged', function(event) {
        updateChartsTheme(event.detail.darkMode);
    });
    
    // Verificar se o modo escuro está ativo e atualizar os gráficos
    if (document.body.classList.contains('night-mode')) {
        updateChartsTheme(true);
    }
    
    // Ajustar padding do conteúdo em relação ao rodapé fixo
    const footer = document.querySelector('.footer');
    const contentBody = document.querySelector('.content-body');
    if (footer && contentBody) {
        contentBody.style.paddingBottom = (footer.offsetHeight + 20) + 'px';
    }
    
    // Detectar a orientação do dispositivo em celulares
    function checkOrientation() {
        if (window.innerWidth < 768 && window.innerHeight < window.innerWidth) {
            showToast('Para uma melhor experiência, rotacione o dispositivo para o modo retrato.', 'info');
        }
    }
    
    // Verificar orientação quando a tela for redimensionada
    window.addEventListener('resize', debounce(checkOrientation, 1000));
    // Verificar orientação inicial
    checkOrientation();
});