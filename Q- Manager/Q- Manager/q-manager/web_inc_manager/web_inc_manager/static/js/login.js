/**
 * Q-Manager - Login Page Script
 * Funcionalidades para a página de login
 */

document.addEventListener('DOMContentLoaded', function() {
    // Variáveis
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const togglePassword = document.querySelector('.password-toggle');
    const loginButton = document.querySelector('.login-button');
    const loginForm = document.querySelector('.login-form');
    const alerts = document.querySelectorAll('.alert');
    const themeToggle = document.getElementById('theme-toggle');
    
    // Alternar visibilidade da senha
    if (togglePassword) {
        togglePassword.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.querySelector('i').classList.toggle('fa-eye');
            this.querySelector('i').classList.toggle('fa-eye-slash');
        });
    }
    
    // Animação do botão de login
    if (loginButton) {
        loginButton.addEventListener('mousedown', function() {
            this.style.transform = 'translateY(0)';
        });
        
        loginButton.addEventListener('mouseup', function() {
            this.style.transform = 'translateY(-2px)';
        });
    }
    
    // Auto-fechar alertas após 5 segundos
    alerts.forEach(function(alert) {
        setTimeout(function() {
            if (alert) {
                const closeButton = new bootstrap.Alert(alert);
                closeButton.close();
            }
        }, 5000);
    });
    
    // Validação em tempo real
    if (usernameInput && passwordInput) {
        // Adicionar classes de validação ao digitar
        usernameInput.addEventListener('input', function() {
            this.classList.remove('is-invalid');
            if (this.value.trim() !== '') {
                this.classList.add('is-valid');
            } else {
                this.classList.remove('is-valid');
            }
            
            // Reabilitar botão se tinha sido desabilitado
            if (loginButton.disabled && this.form.checkValidity()) {
                loginButton.disabled = false;
                loginButton.innerHTML = '<i class="fas fa-sign-in-alt me-2"></i>Entrar';
            }
        });
        
        passwordInput.addEventListener('input', function() {
            this.classList.remove('is-invalid');
            if (this.value.trim() !== '') {
                this.classList.add('is-valid');
            } else {
                this.classList.remove('is-valid');
            }
            
            // Reabilitar botão se tinha sido desabilitado
            if (loginButton.disabled && this.form.checkValidity()) {
                loginButton.disabled = false;
                loginButton.innerHTML = '<i class="fas fa-sign-in-alt me-2"></i>Entrar';
            }
        });
        
        // Validação completa no envio do formulário
        if (loginForm) {
            loginForm.addEventListener('submit', function(event) {
                let isValid = true;
                
                // Validar username
                if (usernameInput.value.trim() === '') {
                    usernameInput.classList.add('is-invalid');
                    isValid = false;
                } else {
                    usernameInput.classList.add('is-valid');
                }
                
                // Validar password
                if (passwordInput.value.trim() === '') {
                    passwordInput.classList.add('is-invalid');
                    isValid = false;
                } else {
                    passwordInput.classList.add('is-valid');
                }
                
                // Se inválido, prevenir envio e reabilitar botão
                if (!isValid) {
                    event.preventDefault();
                    loginButton.disabled = false;
                    loginButton.innerHTML = '<i class="fas fa-sign-in-alt me-2"></i>Entrar';
                    return false;
                }
                
                // Se válido, mostrar loading
                loginButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Entrando...';
                loginButton.disabled = true;
                return true;
            });
        }
    }
    
    // Focar automaticamente no campo de usuário
    if (usernameInput) {
        usernameInput.focus();
    }
    
    // Salvar o nome de usuário no localStorage para facilitar logins futuros
    if (loginForm) {
        // Verificar se há um nome de usuário salvo
        const savedUsername = localStorage.getItem('lastUsername');
        if (savedUsername && usernameInput) {
            usernameInput.value = savedUsername;
            // Mover o foco para o campo de senha
            passwordInput.focus();
        }
        
        // Salvar nome de usuário ao fazer login
        loginForm.addEventListener('submit', function() {
            if (usernameInput.value.trim() !== '') {
                localStorage.setItem('lastUsername', usernameInput.value);
            }
        });
    }
    
    // Fechar alertas ao clicar neles
    alerts.forEach(function(alert) {
        alert.addEventListener('click', function() {
            const closeButton = new bootstrap.Alert(alert);
            closeButton.close();
        });
    });
    
    // Gerenciar tema claro/escuro
    if (themeToggle) {
        // Verificar tema salvo
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('night-mode');
            themeToggle.querySelector('i').classList.replace('fa-moon', 'fa-sun');
        }
        
        // Alternar tema ao clicar no botão
        themeToggle.addEventListener('click', function() {
            document.body.classList.toggle('night-mode');
            
            // Atualizar ícone
            const icon = this.querySelector('i');
            if (document.body.classList.contains('night-mode')) {
                icon.classList.replace('fa-moon', 'fa-sun');
                localStorage.setItem('theme', 'dark');
            } else {
                icon.classList.replace('fa-sun', 'fa-moon');
                localStorage.setItem('theme', 'light');
            }
            
            // Animar o botão
            this.classList.add('animated');
            setTimeout(() => {
                this.classList.remove('animated');
            }, 300);
        });
    }
    
    // Detectar modo escuro do sistema e aplicar tema correspondente (apenas se não houver preferência salva)
    if (!localStorage.getItem('theme')) {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.body.classList.add('night-mode');
            if (themeToggle) {
                themeToggle.querySelector('i').classList.replace('fa-moon', 'fa-sun');
            }
        }
        
        // Observar mudanças no modo escuro do sistema
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem('theme')) { // Aplicar apenas se o usuário não tiver escolhido um tema
                if (e.matches) {
                    document.body.classList.add('night-mode');
                    if (themeToggle) {
                        themeToggle.querySelector('i').classList.replace('fa-moon', 'fa-sun');
                    }
                } else {
                    document.body.classList.remove('night-mode');
                    if (themeToggle) {
                        themeToggle.querySelector('i').classList.replace('fa-sun', 'fa-moon');
                    }
                }
            }
        });
    }
}); 