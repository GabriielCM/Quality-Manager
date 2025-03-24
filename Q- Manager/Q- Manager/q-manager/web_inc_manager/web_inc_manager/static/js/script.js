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
 * Sistema de Notificações
 * @class NotificationSystem
 * @description Gerencia as notificações do sistema
 */
class NotificationSystem {
    constructor() {
        this.initialized = false;
        
        // Elementos de UI
        this.bell = document.querySelector('.notification-bell');
        this.container = document.querySelector('.notification-center');
        this.badge = document.querySelector('.notification-badge');
        this.list = document.querySelector('.notification-list');
        
        // Verificar elementos necessários
        if (!this.bell) {
            console.error('NotificationSystem: Bell não encontrado!');
            return;
        }
        
        if (!this.container) {
            console.error('NotificationSystem: Container não encontrado!');
            return;
        }
        
        if (!this.list) {
            console.error('NotificationSystem: Lista não encontrada!');
            return;
        }
        
        // Estado
        this.notifications = [];
        this.lastCheck = 0;
        this.checkInterval = 10000; // 10 segundos
        this.previousCount = 0; // Armazena contagem anterior para identificar novas notificações
        this.soundEnabled = localStorage.getItem('notification_sound_enabled') !== 'false';
        this.initialLoad = true; // Flag para identificar o carregamento inicial da página
        this.notificationIds = new Set(); // Armazena IDs de notificações já carregadas
        
        // Inicializar o som de notificação (com fallback se o arquivo não existir)
        try {
            this.notificationSound = new Audio('/static/sounds/notification.mp3');
            
            // Adicionar tratamento de erro para caso o arquivo não exista
            this.notificationSound.onerror = () => {
                console.warn('Arquivo de som de notificação não encontrado. Usando fallback.');
                // Criar um som de beep usando o AudioContext API
                this.createFallbackSound();
            };
            
            // Pré-carregar o som
            this.notificationSound.load();
        } catch (e) {
            console.warn('Erro ao inicializar som de notificação:', e);
            this.createFallbackSound();
        }
        
        this.mockNotifications = [
            { 
                id: 1, 
                title: 'Novo chamado', 
                message: 'Um novo chamado foi aberto: #12345', 
                timestamp: new Date(Date.now() - 5 * 60000), 
                read: false, 
                category: 'task',
                actionUrl: '/inc/detalhes_inc/12345',
                actionText: 'Visualizar chamado'
            },
            { 
                id: 2, 
                title: 'Atualização do sistema', 
                message: 'O sistema foi atualizado para a versão 2.0', 
                timestamp: new Date(Date.now() - 60 * 60000), 
                read: false, 
                category: 'system',
                actionUrl: '/changelog',
                actionText: 'Ver novidades'
            },
            { 
                id: 3, 
                title: 'Lembrete', 
                message: 'Reunião de equipe em 30 minutos', 
                timestamp: new Date(Date.now() - 24 * 60 * 60000), 
                read: true, 
                category: 'reminder',
                actionUrl: '/calendario',
                actionText: 'Ver agenda'
            }
        ];
        
        console.log('NotificationSystem: Elementos encontrados com sucesso');
    }
    
    /**
     * Cria um som de fallback usando a Web Audio API
     */
    createFallbackSound() {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                const audioCtx = new AudioContext();
                
                // Armazena uma função que cria um beep simples
                this.notificationSound = {
                    play: () => {
                        const oscillator = audioCtx.createOscillator();
                        const gainNode = audioCtx.createGain();
                        
                        oscillator.connect(gainNode);
                        gainNode.connect(audioCtx.destination);
                        
                        oscillator.type = 'sine';
                        oscillator.frequency.value = 880; // A5
                        
                        gainNode.gain.value = 0.1;
                        
                        oscillator.start();
                        
                        // Fade out
                        gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);
                        
                        // Parar depois de 0.5 segundos
                        setTimeout(() => {
                            oscillator.stop();
                        }, 500);
                        
                        return Promise.resolve();
                    }
                };
            } else {
                console.warn('AudioContext não suportado neste navegador');
                // Objeto vazio com método play que retorna uma Promise resolvida
                this.notificationSound = { play: () => Promise.resolve() };
            }
        } catch (e) {
            console.warn('Erro ao criar som de fallback:', e);
            // Objeto vazio com método play que retorna uma Promise resolvida
            this.notificationSound = { play: () => Promise.resolve() };
        }
    }
    
    /**
     * Inicializa o sistema de notificações
     */
    init() {
        if (this.initialized) {
            console.warn('NotificationSystem já inicializado!');
            return;
        }
        
        // Adicionar evento de clique no sino
        this.bell.addEventListener('click', () => {
            this.toggleNotificationCenter();
            console.log('Notificações toggles. Estado:', this.container.classList.contains('show'));
        });
        
        // Fechar ao clicar fora
        document.addEventListener('click', (e) => {
            if (this.container && 
                this.container.classList.contains('show') && 
                !this.container.contains(e.target) && 
                e.target !== this.bell) {
                this.container.classList.remove('show');
            }
        });
        
        // Botão "Marcar todas como lidas"
        const markAllBtn = this.container.querySelector('.mark-all-read');
        if (markAllBtn) {
            markAllBtn.addEventListener('click', () => {
                this.markAllAsRead();
            });
        } else {
            console.warn('NotificationSystem: Botão "Marcar todas como lidas" não encontrado');
        }
        
        // Adicionar controle de som
        const soundToggle = document.createElement('button');
        soundToggle.className = 'btn btn-sm btn-outline-secondary ms-2';
        soundToggle.innerHTML = `<i class="fas fa-${this.soundEnabled ? 'volume-up' : 'volume-mute'}"></i>`;
        soundToggle.title = this.soundEnabled ? 'Desativar som' : 'Ativar som';
        soundToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleSound();
            soundToggle.innerHTML = `<i class="fas fa-${this.soundEnabled ? 'volume-up' : 'volume-mute'}"></i>`;
            soundToggle.title = this.soundEnabled ? 'Desativar som' : 'Ativar som';
        });
        
        // Adicionar controle de som ao cabeçalho de notificações
        const headerActions = this.container.querySelector('.notification-header-actions');
        if (headerActions) {
            headerActions.appendChild(soundToggle);
        } else {
            const header = this.container.querySelector('.notification-header');
            if (header) {
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'notification-header-actions';
                actionsDiv.appendChild(soundToggle);
                header.appendChild(actionsDiv);
            }
        }
        
        // Configurar filtros de notificação
        this.setupFilters();
        
        // Verificar notificações imediatamente e depois periodicamente
        this.checkNotifications();
        setInterval(() => this.checkNotifications(), this.checkInterval);
        
        this.initialized = true;
        console.log('NotificationSystem: Inicializado com sucesso ✅');
    }
    
    /**
     * Configura os filtros de notificação
     */
    setupFilters() {
        // Recuperar filtro salvo
        this.currentFilter = localStorage.getItem('notification_filter') || 'all';
        
        // Configurar botões de filtro
        const filterButtons = this.container.querySelectorAll('.notification-filters button');
        if (filterButtons.length) {
            filterButtons.forEach(button => {
                // Definir estado inicial
                if (button.dataset.filter === this.currentFilter) {
                    button.classList.add('active');
                } else {
                    button.classList.remove('active');
                }
                
                // Adicionar eventos
                button.addEventListener('click', () => {
                    // Remover classe ativa de todos os botões
                    filterButtons.forEach(btn => btn.classList.remove('active'));
                    
                    // Adicionar classe ativa ao botão clicado
                    button.classList.add('active');
                    
                    // Atualizar filtro atual
                    this.currentFilter = button.dataset.filter;
                    localStorage.setItem('notification_filter', this.currentFilter);
                    
                    // Renderizar novamente com o novo filtro
                    this.render();
                });
            });
        } else {
            console.warn('NotificationSystem: Botões de filtro não encontrados');
        }
    }
    
    /**
     * Alterna a visibilidade do centro de notificações
     */
    toggleNotificationCenter() {
        if (!this.container) return;
        
        // Alternar entre exibir e ocultar
        this.container.classList.toggle('show');
        
        // Manter compatibilidade com versões antigas
        if (this.container.classList.contains('show')) {
            this.container.classList.add('open');
            // Se estiver abrindo, esconder badge
            if (this.badge) {
                this.badge.classList.add('d-none');
            }
            console.log('Centro de notificações aberto');
        } else {
            this.container.classList.remove('open');
            console.log('Centro de notificações fechado');
        }
    }
    
    /**
     * Ativa ou desativa o som das notificações
     */
    toggleSound() {
        this.soundEnabled = !this.soundEnabled;
        localStorage.setItem('notification_sound_enabled', this.soundEnabled);
        
        // Tocar um som para demonstrar
        if (this.soundEnabled) {
            this.notificationSound.volume = 0.5;
            this.notificationSound.play().catch(err => console.warn('Erro ao tocar som:', err));
        }
        
        console.log(`Som de notificações ${this.soundEnabled ? 'ativado' : 'desativado'}`);
    }
    
    /**
     * Reproduz o som de notificação
     */
    playNotificationSound() {
        if (!this.soundEnabled) return;
        
        // Reproduz o som se estiver ativado
        this.notificationSound.volume = 0.5;
        this.notificationSound.play().catch(err => console.warn('Erro ao tocar som:', err));
    }
    
    /**
     * Anima o ícone de notificação para chamar atenção
     */
    animateNotificationIcon() {
        if (!this.bell) return;
        
        // Adiciona classe para animação
        this.bell.classList.add('shake-animation');
        
        // Remove a classe após a animação terminar
        setTimeout(() => {
            this.bell.classList.remove('shake-animation');
        }, 1000);
        
        // Anima o badge também
        if (this.badge) {
            this.badge.classList.add('animate');
            setTimeout(() => {
                this.badge.classList.remove('animate');
            }, 1000);
        }
    }
    
    /**
     * Verifica novas notificações
     */
    async checkNotifications() {
        const now = Date.now();
        
        // Evitar requisições muito frequentes
        if (now - this.lastCheck < this.checkInterval) {
            return;
        }
        
        this.lastCheck = now;
        
        // Armazenar IDs das notificações atuais para comparação
        const currentNotificationIds = new Set(this.notifications.map(n => n.id));
        
        try {
            // Tentar buscar notificações da API
            const response = await fetch('/api/notificacoes');
            if (response.ok) {
                const data = await response.json();
                
                // Verificar se existem novas notificações comparando com as atuais
                const newNotifications = data.filter(n => !this.notificationIds.has(n.id));
                
                // Atualizar notificações
                this.notifications = data;
                console.log('NotificationSystem: Notificações recebidas da API:', data.length);
                
                // Se não é a carga inicial e temos novas notificações
                if (!this.initialLoad && newNotifications.length > 0) {
                    // Reproduzir som
                    this.playNotificationSound();
                    
                    // Animar ícone
                    this.animateNotificationIcon();
                    
                    // Exibir notificação do sistema para a primeira notificação nova (mais recente)
                    if (newNotifications.length > 0) {
                        this.showSystemNotification(newNotifications[0]);
                    }
                }
                
                // Armazenar os IDs de notificações atuais
                this.notificationIds = new Set(data.map(n => n.id));
            } else {
                // Em caso de erro, usar notificações de exemplo em ambiente de desenvolvimento
                if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                    console.warn('NotificationSystem: Usando notificações de exemplo (desenvolvimento)');
                    this.notifications = this.mockNotifications;
                } else {
                    console.error('NotificationSystem: Erro ao buscar notificações:', response.status);
                }
            }
        } catch (error) {
            // Em caso de erro, usar notificações de exemplo em ambiente de desenvolvimento
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.warn('NotificationSystem: Usando notificações de exemplo (desenvolvimento)');
                this.notifications = this.mockNotifications;
            } else {
                console.error('NotificationSystem: Erro ao buscar notificações:', error);
            }
        }
        
        // Marcar que o carregamento inicial foi concluído
        this.initialLoad = false;
        
        // Atualizar a interface
        this.render();
    }
    
    /**
     * Exibe uma notificação do sistema (notificação nativa do navegador)
     * @param {Object} notification - A notificação a ser exibida
     */
    showSystemNotification(notification) {
        // Verificar se o navegador suporta notificações
        if (!("Notification" in window)) {
            return;
        }
        
        // Verificar permissão
        if (Notification.permission === "granted") {
            if (notification) {
                const systemNotification = new Notification("Q-Manager", {
                    body: notification.message,
                    icon: "/static/img/logo-icon.png"
                });
                
                // Fechar após 5 segundos
                setTimeout(() => systemNotification.close(), 5000);
                
                // Ao clicar, redirecionar para a ação se disponível
                systemNotification.onclick = () => {
                    window.focus();
                    if (notification.actionUrl) {
                        window.location.href = notification.actionUrl;
                    } else {
                        this.container.classList.add('show');
                    }
                };
            }
        }
        // Se a permissão não foi decidida, solicitar
        else if (Notification.permission !== "denied") {
            Notification.requestPermission();
        }
    }
    
    /**
     * Marca uma notificação como lida
     * @param {number} id - ID da notificação
     */
    async markAsRead(id) {
        try {
            // Tentar marcar como lida na API
            const response = await fetch('/api/notificacoes/marcar-lida', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ id })
            });
            
            if (!response.ok) {
                console.error('NotificationSystem: Erro ao marcar notificação como lida:', response.status);
            }
        } catch (error) {
            console.error('NotificationSystem: Erro ao marcar notificação como lida:', error);
        }
        
        // Atualizar localmente
        this.notifications = this.notifications.map(n => 
            n.id === id ? { ...n, read: true } : n
        );
        
        // Atualizar a interface
        this.render();
    }
    
    /**
     * Marca todas as notificações como lidas
     */
    async markAllAsRead() {
        try {
            // Tentar marcar todas como lidas na API
            const response = await fetch('/api/notificacoes/marcar-todas-lidas', {
                method: 'POST'
            });
            
            if (!response.ok) {
                console.error('NotificationSystem: Erro ao marcar todas as notificações como lidas:', response.status);
            }
        } catch (error) {
            console.error('NotificationSystem: Erro ao marcar todas as notificações como lidas:', error);
        }
        
        // Atualizar localmente
        this.notifications = this.notifications.map(n => ({ ...n, read: true }));
        
        // Atualizar a interface
        this.render();
    }
    
    /**
     * Obtém o ícone correspondente à categoria da notificação
     * @param {string} category - Categoria da notificação
     * @returns {string} - Classe de ícone FontAwesome
     */
    getCategoryIcon(category) {
        switch(category) {
            case 'task':
                return 'fa-tasks';
            case 'system':
                return 'fa-cog';
            case 'alert':
                return 'fa-exclamation-triangle';
            case 'message':
                return 'fa-comment';
            case 'reminder':
                return 'fa-clock';
            case 'update':
                return 'fa-sync';
            default:
                return 'fa-bell';
        }
    }
    
    /**
     * Obtém a cor correspondente à categoria da notificação
     * @param {string} category - Categoria da notificação
     * @returns {string} - Nome da classe de cor
     */
    getCategoryColorClass(category) {
        switch(category) {
            case 'task':
                return 'text-primary';
            case 'system':
                return 'text-info';
            case 'alert':
                return 'text-danger';
            case 'message':
                return 'text-success';
            case 'reminder':
                return 'text-warning';
            case 'update':
                return 'text-secondary';
            default:
                return 'text-dark';
        }
    }
    
    /**
     * Atualiza a interface com as notificações atuais
     */
    render() {
        if (!this.list || !this.badge) return;
        
        // Limpar lista
        this.list.innerHTML = '';
        
        // Verificar se há notificações não lidas
        const unreadCount = this.notifications.filter(n => !n.read).length;
        
        // Atualizar badge
        if (unreadCount > 0) {
            this.badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
            this.badge.classList.remove('d-none');
        } else {
            this.badge.classList.add('d-none');
        }
        
        // Ordenar notificações (não lidas primeiro, depois por data)
        const sortedNotifications = [...this.notifications].sort((a, b) => {
            if (a.read !== b.read) return a.read ? 1 : -1;
            return new Date(b.timestamp) - new Date(a.timestamp);
        });
        
        // Filtrar notificações conforme seleção
        let filteredNotifications = sortedNotifications;
        if (this.currentFilter === 'unread') {
            filteredNotifications = sortedNotifications.filter(n => !n.read);
        }
        
        // Adicionar notificações à lista
        if (filteredNotifications.length === 0) {
            const emptyItem = document.createElement('li');
            emptyItem.className = 'notification-item empty';
            emptyItem.textContent = this.currentFilter === 'unread' ? 
                'Nenhuma notificação não lida.' : 
                'Nenhuma notificação.';
            this.list.appendChild(emptyItem);
        } else {
            filteredNotifications.forEach((notification, index) => {
                const item = document.createElement('li');
                item.className = `notification-item ${notification.read ? 'read' : 'unread'}`;
                
                // Adicionar animação para novas notificações (somente as mais recentes)
                if (!notification.read && index < 3) {
                    item.classList.add('animate-new');
                    
                    // Remover a classe de animação após a animação terminar
                    setTimeout(() => {
                        item.classList.remove('animate-new');
                    }, 500 + (index * 200)); // Escalonar animações
                }
                
                // Ícone de categoria
                const icon = document.createElement('div');
                icon.className = `notification-icon ${this.getCategoryColorClass(notification.category)}`;
                const iconEl = document.createElement('i');
                iconEl.className = `fas ${this.getCategoryIcon(notification.category)}`;
                icon.appendChild(iconEl);
                
                const content = document.createElement('div');
                content.className = 'notification-content';
                
                const title = document.createElement('div');
                title.className = 'notification-title';
                title.textContent = notification.title;
                
                const message = document.createElement('div');
                message.className = 'notification-message';
                message.textContent = notification.message;
                
                const time = document.createElement('div');
                time.className = 'notification-time';
                time.textContent = this.formatTimestamp(notification.timestamp);
                
                content.appendChild(title);
                content.appendChild(message);
                content.appendChild(time);
                
                // Área de ações
                const actions = document.createElement('div');
                actions.className = 'notification-actions';
                
                // Botão de marcar como lido se não estiver lido
                if (!notification.read) {
                    const markAsReadBtn = document.createElement('button');
                    markAsReadBtn.className = 'btn btn-sm btn-outline-primary';
                    markAsReadBtn.innerHTML = '<i class="fas fa-check"></i>';
                    markAsReadBtn.title = 'Marcar como lida';
                    markAsReadBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.markAsRead(notification.id);
                    });
                    actions.appendChild(markAsReadBtn);
                }
                
                // Adicionar evento de clique conforme a ação disponível
                if (notification.actionUrl) {
                    // Se tem URL de ação, adiciona link para a URL
                    item.style.cursor = 'pointer';
                    item.addEventListener('click', () => {
                        // Marcar como lida antes de redirecionar
                        if (!notification.read) {
                            this.markAsRead(notification.id);
                        }
                        // Redirecionar para a URL da ação
                        window.location.href = notification.actionUrl;
                    });
                    
                    // Adicionar botão de ação se tiver texto de ação
                    if (notification.actionText) {
                        const actionBtn = document.createElement('a');
                        actionBtn.href = notification.actionUrl;
                        actionBtn.className = 'btn btn-sm btn-primary ms-2';
                        actionBtn.innerHTML = `<i class="fas fa-arrow-right me-1"></i>${notification.actionText}`;
                        actionBtn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            // Marcar como lida antes de seguir o link
                            if (!notification.read) {
                                this.markAsRead(notification.id);
                            }
                        });
                        actions.appendChild(actionBtn);
                    }
                } else {
                    // Se não tem URL de ação, apenas marca como lida ao clicar
                    item.addEventListener('click', () => {
                        if (!notification.read) {
                            this.markAsRead(notification.id);
                        }
                    });
                }
                
                item.appendChild(icon);
                item.appendChild(content);
                item.appendChild(actions);
                
                this.list.appendChild(item);
            });
        }
    }
    
    /**
     * Formata o timestamp para exibição
     * @param {Date|string} timestamp - Data e hora da notificação 
     * @returns {string} Tempo relativo formatado
     */
    formatTimestamp(timestamp) {
        const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);
        
        if (diffSec < 60) {
            return 'Agora mesmo';
        } else if (diffMin < 60) {
            return `${diffMin} minuto${diffMin > 1 ? 's' : ''} atrás`;
        } else if (diffHour < 24) {
            return `${diffHour} hora${diffHour > 1 ? 's' : ''} atrás`;
        } else if (diffDay < 7) {
            return `${diffDay} dia${diffDay > 1 ? 's' : ''} atrás`;
        } else {
            return date.toLocaleDateString('pt-BR');
        }
    }
}

// ===== SISTEMA DE TEMAS =====

/**
 * Sistema de Temas
 * @class ThemeSystem
 * @description Gerencia os temas do sistema, incluindo modo noturno e seleção de fontes
 */
class ThemeSystem {
    constructor() {
        this.initialized = false;
        
        // Elementos de UI
        this.themeButton = document.getElementById('theme-toggle');
        this.themePanel = document.querySelector('.theme-panel');
        this.themeOptions = document.querySelectorAll('.theme-option');
        this.darkModeSwitch = document.getElementById('darkModeSwitch');
        this.nightModeButton = document.getElementById('toggleNightMode');
        this.fontSelector = document.getElementById('fontSelector');
        
        // Verificar elementos necessários
        if (!this.themeButton) {
            console.error('Botão de tema não encontrado!');
            return;
        }
        
        if (!this.themePanel) {
            console.error('Painel de tema não encontrado!');
            return;
        }
        
        console.log('ThemeSystem: Elementos encontrados com sucesso');
    }
    
    /**
     * Inicializa o sistema de temas
     */
    init() {
        if (this.initialized) {
            console.warn('ThemeSystem já inicializado!');
            return;
        }
        
        // Carregar tema salvo
        this.loadSavedTheme();
        
        // Event listener para o botão de tema
        this.themeButton.addEventListener('click', () => {
            this.toggleThemePanel();
        });
        
        // Fechar o painel de temas ao clicar fora
        document.addEventListener('click', (e) => {
            if (this.themePanel && 
                !this.themePanel.contains(e.target) && 
                e.target !== this.themeButton && 
                this.themePanel.classList.contains('show')) {
                this.themePanel.classList.remove('show');
                this.themeButton.setAttribute('aria-expanded', 'false');
                console.log('Painel de temas fechado (clique fora)');
            }
        });
        
        // Event listeners para cada opção de tema
        this.themeOptions.forEach(option => {
            option.addEventListener('click', () => {
                const theme = option.getAttribute('data-theme');
                this.applyTheme(theme);
                
                // Atualizar seleção visual
                this.themeOptions.forEach(opt => {
                    opt.setAttribute('aria-selected', 'false');
                    opt.classList.remove('selected');
                });
                option.setAttribute('aria-selected', 'true');
                option.classList.add('selected');
                
                console.log(`Tema alterado para: ${theme}`);
                this.themePanel.classList.remove('show');
                this.themeButton.setAttribute('aria-expanded', 'false');
            });
            
            // Adicionar suporte para navegação por teclado
            option.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    option.click();
                }
            });
        });
        
        // Event listener para o dark mode switch
        if (this.darkModeSwitch) {
            this.darkModeSwitch.addEventListener('change', () => {
                this.toggleDarkMode();
                console.log(`Modo escuro: ${this.darkModeSwitch.checked ? 'ativado' : 'desativado'}`);
            });
        }
        
        // Event listener para o botão de modo noturno
        if (this.nightModeButton) {
            this.nightModeButton.addEventListener('click', () => {
                if (this.darkModeSwitch) {
                    this.darkModeSwitch.checked = !this.darkModeSwitch.checked;
                }
                this.toggleDarkMode();
                console.log(`Modo noturno alterado por botão`);
            });
        }
        
        // Event listener para o seletor de fonte
        if (this.fontSelector) {
            this.fontSelector.addEventListener('change', () => {
                const font = this.fontSelector.value;
                document.documentElement.style.setProperty('--font-family', font);
                localStorage.setItem('fontFamily', font);
                console.log(`Fonte alterada para: ${font}`);
            });
            
            // Carregar fonte salva
            const savedFont = localStorage.getItem('fontFamily');
            if (savedFont) {
                this.fontSelector.value = savedFont;
                document.documentElement.style.setProperty('--font-family', savedFont);
            }
        }
        
        // Marcar como inicializado
        this.initialized = true;
        console.log('ThemeSystem: Inicializado com sucesso ✅');
    }
    
    /**
     * Alterna a visibilidade do painel de temas
     */
    toggleThemePanel() {
        if (!this.themePanel) return;
        
        // Alternar entre exibir e ocultar
        const isExpanded = this.themePanel.classList.contains('show');
        
        if (isExpanded) {
            this.themePanel.classList.remove('show');
            this.themePanel.classList.remove('open'); // Compatibilidade com versões antigas
            this.themeButton.setAttribute('aria-expanded', 'false');
            console.log('Painel de temas fechado');
        } else {
            this.themePanel.classList.add('show');
            this.themePanel.classList.add('open'); // Compatibilidade com versões antigas
            this.themeButton.setAttribute('aria-expanded', 'true');
            console.log('Painel de temas aberto');
        }
    }
    
    /**
     * Aplica o tema selecionado
     * @param {string} theme - Nome do tema a ser aplicado
     */
    applyTheme(theme) {
        document.body.className = document.body.className.replace(/theme-\w+/, '');
        document.body.classList.add(`theme-${theme}`);
        localStorage.setItem('theme', theme);
        
        // Se estivermos no modo escuro, reaplique-o
        if (localStorage.getItem('nightMode') === 'true') {
            document.body.classList.add('dark-mode');
        }
    }
    
    /**
     * Carrega o tema salvo no localStorage
     */
    loadSavedTheme() {
        const savedTheme = localStorage.getItem('theme') || 'default';
        this.applyTheme(savedTheme);
        
        // Selecionar visualmente a opção do tema
        this.themeOptions.forEach(option => {
            const optionTheme = option.getAttribute('data-theme');
            if (optionTheme === savedTheme) {
                option.setAttribute('aria-selected', 'true');
                option.classList.add('selected');
            } else {
                option.setAttribute('aria-selected', 'false');
                option.classList.remove('selected');
            }
        });
        
        // Carregar modo noturno
        const nightMode = localStorage.getItem('nightMode') === 'true';
        if (this.darkModeSwitch) {
            this.darkModeSwitch.checked = nightMode;
        }
        
        if (nightMode) {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
    }
    
    /**
     * Alterna entre modo claro e escuro
     */
    toggleDarkMode() {
        const isDarkMode = document.body.classList.toggle('dark-mode');
        localStorage.setItem('nightMode', isDarkMode);
        
        // Atualizar ícone do botão de modo noturno
        if (this.nightModeButton) {
            const iconElement = this.nightModeButton.querySelector('i');
            if (iconElement) {
                if (isDarkMode) {
                    iconElement.classList.remove('fa-moon');
                    iconElement.classList.add('fa-sun');
                } else {
                    iconElement.classList.remove('fa-sun');
                    iconElement.classList.add('fa-moon');
                }
            }
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
    Chart.defaults.color = isDarkMode ? '#f8f9fa' : '#666';
    Chart.defaults.borderColor = isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)';
    
    // Cores para os gráficos com melhor contraste
    const darkModeColors = [
        'rgba(26, 188, 156, 0.8)',    // Esmeralda forte
        'rgba(46, 204, 113, 0.8)',    // Verde mais visível
        'rgba(52, 152, 219, 0.8)',    // Azul mais visível
        'rgba(155, 89, 182, 0.8)',    // Roxo mais visível
        'rgba(241, 196, 15, 0.8)',    // Amarelo claro
        'rgba(230, 126, 34, 0.8)'     // Laranja mais visível
    ];
    
    const lightModeColors = [
        'rgba(26, 188, 156, 0.7)',    // Esmeralda
        'rgba(46, 204, 113, 0.7)',    // Verde
        'rgba(52, 152, 219, 0.7)',    // Azul
        'rgba(155, 89, 182, 0.7)',    // Roxo
        'rgba(241, 196, 15, 0.7)',    // Amarelo
        'rgba(230, 126, 34, 0.7)'     // Laranja
    ];
    
    // Atualizar todos os gráficos na página
    Chart.instances.forEach(chart => {
        // Aplicar cores apropriadas para o modo atual
        const datasets = chart.config.data.datasets;
        if (datasets && datasets.length > 0) {
            datasets.forEach((dataset, index) => {
                if (dataset.type === 'line') {
                    dataset.borderColor = isDarkMode ? darkModeColors[index % darkModeColors.length] : lightModeColors[index % lightModeColors.length];
                    dataset.pointBackgroundColor = dataset.borderColor;
                } else {
                    dataset.backgroundColor = isDarkMode ? darkModeColors[index % darkModeColors.length] : lightModeColors[index % lightModeColors.length];
                }
            });
        }
        
        // Configurações de grade para melhor visibilidade
        if (chart.config.options && chart.config.options.scales) {
            const scales = chart.config.options.scales;
            
            if (scales.x) {
                scales.x.grid = {
                    color: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
                    drawBorder: true,
                    borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)'
                };
            }
            
            if (scales.y) {
                scales.y.grid = {
                    color: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
                    drawBorder: true,
                    borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)'
                };
            }
        }
        
        chart.update();
    });
}

/**
 * Função para diagnóstico de elementos do sistema de notificações
 */
function checkNotificationElements() {
    console.log('==== DIAGNÓSTICO DE NOTIFICAÇÕES ====');
    
    const bell = document.querySelector('.notification-bell');
    const container = document.querySelector('.notification-center');
    const badge = document.querySelector('.notification-badge');
    const list = document.querySelector('.notification-list');
    const markAllBtn = document.querySelector('.mark-all-read');
    
    console.log('Bell:', bell ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    console.log('Container:', container ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    console.log('Badge:', badge ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    console.log('List:', list ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    console.log('Mark All Button:', markAllBtn ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    
    if (bell) {
        console.log('Bell classes:', bell.className);
        console.log('Bell HTML:', bell.outerHTML);
    }
    
    if (container) {
        console.log('Container classes:', container.className);
        console.log('Container é visível:', !container.classList.contains('d-none') && container.offsetParent !== null);
    }
    
    return { bell, container, badge, list, markAllBtn };
}

/**
 * Função para diagnóstico de elementos do sistema de temas
 */
function checkThemeElements() {
    console.log('==== DIAGNÓSTICO DE TEMAS ====');
    
    const themeToggle = document.getElementById('theme-toggle');
    const themePanel = document.querySelector('.theme-panel');
    const themeOptions = document.querySelectorAll('.theme-option');
    const darkModeSwitch = document.getElementById('darkModeSwitch');
    const toggleNightMode = document.getElementById('toggleNightMode');
    
    console.log('Theme Toggle Button:', themeToggle ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    console.log('Theme Panel:', themePanel ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    console.log('Theme Options:', themeOptions.length > 0 ? `✅ Encontradas (${themeOptions.length})` : '❌ NÃO ENCONTRADAS');
    console.log('Dark Mode Switch:', darkModeSwitch ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    console.log('Night Mode Toggle Button:', toggleNightMode ? '✅ Encontrado' : '❌ NÃO ENCONTRADO');
    
    if (themeToggle) {
        console.log('Theme Toggle classes:', themeToggle.className);
        console.log('Theme Toggle HTML:', themeToggle.outerHTML);
    }
    
    if (themePanel) {
        console.log('Theme Panel classes:', themePanel.className);
        console.log('Theme Panel é visível:', !themePanel.classList.contains('d-none') && themePanel.offsetParent !== null);
    }
    
    return { themeToggle, themePanel, themeOptions, darkModeSwitch, toggleNightMode };
}

/**
 * Adiciona ou atualiza uma regra de estilo CSS dinamicamente
 * @param {string} selector - seletor CSS
 * @param {string} rules - regras de estilo
 */
function addOrUpdateCSSRule(selector, rules) {
    // Verificar se já existe uma folha de estilo dinâmica
    let styleSheet = document.getElementById('dynamic-styles');
    
    if (!styleSheet) {
        // Criar uma nova folha de estilo se não existir
        styleSheet = document.createElement('style');
        styleSheet.id = 'dynamic-styles';
        document.head.appendChild(styleSheet);
    }
    
    // Verificar se a regra já existe
    const existingRules = Array.from(styleSheet.sheet?.cssRules || []);
    const existingRuleIndex = existingRules.findIndex(rule => 
        rule.selectorText === selector
    );
    
    if (existingRuleIndex >= 0) {
        // Substituir a regra existente
        styleSheet.sheet.deleteRule(existingRuleIndex);
    }
    
    // Adicionar a nova regra
    styleSheet.sheet.insertRule(`${selector} { ${rules} }`, 
        styleSheet.sheet.cssRules.length);
    
    console.log(`CSS Rule ${existingRuleIndex >= 0 ? 'atualizada' : 'adicionada'}: ${selector}`);
}

/**
 * Aplica correções CSS para compatibilidade com navegadores e melhorias de UI
 */
function applyCSSTweaks() {
    console.log('Aplicando ajustes de CSS para melhorar compatibilidade...');
    
    // Corrigir problemas de z-index
    addOrUpdateCSSRule('.theme-selector', 'z-index: 1060 !important;');
    addOrUpdateCSSRule('.theme-panel', 'z-index: 1061 !important;');
    addOrUpdateCSSRule('.notification-center', 'z-index: 1059 !important;');
    
    // Melhorar visibilidade no modo escuro
    addOrUpdateCSSRule('.dark-mode .notification-item', 'background-color: #2c3e50 !important; color: #ecf0f1 !important;');
    addOrUpdateCSSRule('.dark-mode .theme-panel', 'background-color: #2c3e50 !important; color: #ecf0f1 !important;');
    
    // Corrigir problema de tema-toggle
    addOrUpdateCSSRule('.theme-toggle', 'display: flex !important; align-items: center !important; justify-content: center !important;');
    
    // Garantir que open e show são ambos suportados
    addOrUpdateCSSRule('.theme-panel.open', 'display: block !important;');
    addOrUpdateCSSRule('.theme-panel.show', 'display: block !important;');
    addOrUpdateCSSRule('.notification-center.open', 'display: block !important;');
    addOrUpdateCSSRule('.notification-center.show', 'display: block !important;');
    
    console.log('Ajustes de CSS aplicados com sucesso');
}

// Inicializar sistemas do Q-Manager
document.addEventListener('DOMContentLoaded', function() {
    console.log('%c Q-Manager - Inicialização ', 'background: #3498db; color: white; padding: 5px; border-radius: 3px; font-weight: bold');
    console.log('DOM carregado, inicializando sistemas...');
    
    // Aplicar correções de CSS imediatamente
    applyCSSTweaks();
    
    // Diagnóstico de elementos
    setTimeout(checkThemeElements, 500);
    setTimeout(checkNotificationElements, 500);
    
    // Sistema de Notificações
    try {
        const notificationSystem = new NotificationSystem();
        notificationSystem.init();
        window.notificationSystem = notificationSystem; // Para acesso no console para debug
        console.log('Sistema de notificações inicializado ✅');
    } catch (error) {
        console.error('Erro ao inicializar sistema de notificações:', error);
    }
    
    // Sistema de Temas
    try {
        const themeSystem = new ThemeSystem();
        themeSystem.init();
        window.themeSystem = themeSystem; // Para acesso no console para debug
        console.log('Sistema de temas inicializado ✅');
    } catch (error) {
        console.error('Erro ao inicializar sistema de temas:', error);
    }
    
    // Sistema de Tags
    const tagSystem = new TagSystem();
    
    // Gestor do Kanban
    if (document.querySelector('.kanban-board')) {
        const kanbanManager = new KanbanManager();
    }
    
    // Inicializar tooltips do Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Restaurar posição de scroll
    const savedScrollPosition = localStorage.getItem('scrollPosition');
    if (savedScrollPosition) {
        window.scrollTo(0, parseInt(savedScrollPosition));
    }
    
    // Salvar posição de scroll ao sair
    window.addEventListener('beforeunload', function() {
        localStorage.setItem('scrollPosition', window.scrollY);
    });
    
    // Verificar o estado atual dos elementos após a inicialização completa
    setTimeout(function() {
        console.log('%c Diagnóstico final após inicialização ', 'background: #2ecc71; color: white; padding: 5px; border-radius: 3px; font-weight: bold');
        checkThemeElements();
        checkNotificationElements();
        
        // Verificar classes no body
        console.log('Classes no body:', document.body.className);
        
        // Verificar localStorage
        console.log('LocalStorage - theme:', localStorage.getItem('theme'));
        console.log('LocalStorage - nightMode:', localStorage.getItem('nightMode'));
        console.log('LocalStorage - fontFamily:', localStorage.getItem('fontFamily'));
    }, 1000);
});