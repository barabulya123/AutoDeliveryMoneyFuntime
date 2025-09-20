const mineflayer = require('mineflayer');

class SimpleFuntimeBot {
    constructor() {
        this.bot = null;
        this.isConnected = false;
        this.config = {
            username: 'unk',
            password: 'unk',
            anarchy: 'an210',
            host: 'funtime.su',
            port: 25565,
            version: '1.19.4'
        };
        // Try to load live JSON config saved by the Python plugin
        try {
            const fs = require('fs');
            const path = require('path');
            const cfgPath = path.join(__dirname, '..', '..', 'storage', 'cache', 'minecraft_currency_config.json');
            if (fs.existsSync(cfgPath)) {
                const raw = fs.readFileSync(cfgPath, { encoding: 'utf8' });
                const json = JSON.parse(raw || '{}');
                if (json.minecraft_bot) {
                    const mb = json.minecraft_bot;
                    this.config.username = mb.bot_username || this.config.username;
                    this.config.password = mb.password || this.config.password;
                    this.config.anarchy = mb.anarchy || this.config.anarchy;
                    this.config.host = mb.server || this.config.host;
                    this.config.port = mb.port || this.config.port;
                }
            }
        } catch (e) {
            // fallback to defaults
        }
    }

    async connect() {
        if (this.isConnected) {
            return true;
        }

        try {
            this.bot = mineflayer.createBot({
                host: this.config.host,
                port: this.config.port,
                username: this.config.username,
                password: this.config.password,
                version: this.config.version,
                auth: 'offline'
            });

            this.setupEventHandlers();

            return new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('Connection timeout'));
                }, 30000);

                this.bot.once('spawn', () => {
                    clearTimeout(timeout);
                    this.isConnected = true;
                    resolve(true);
                });

                this.bot.once('error', (err) => {
                    clearTimeout(timeout);
                    reject(err);
                });
            });
        } catch (error) {
            return false;
        }
    }

    setupEventHandlers() {
        this.bot.on('spawn', () => {
            // Авторизация на анархии
            setTimeout(() => {
                const loginCmd = this.config.anarchy ? `/login ${this.config.anarchy}` : '/login an210';
                this.bot.chat(loginCmd);
            }, 2000);
            
            // Переход на 210 анархию
            setTimeout(() => {
                const anarCmd = this.config.anarchy ? `/${this.config.anarchy}` : '/an210';
                this.bot.chat(anarCmd);
            }, 4000);
        });

        this.bot.on('error', (err) => {
            this.isConnected = false;
        });

        this.bot.on('end', () => {
            this.isConnected = false;
        });

        this.bot.on('kicked', (reason) => {
            this.isConnected = false;
        });
    }

    async giveMoney(playerName, amount) {
        if (!this.isConnected) {
            throw new Error('Bot not connected');
        }

        try {
            // Ждем стабилизации подключения
            await this.delay(3000);
            
            // Переходим на правильную анархию
            const anarCmd = this.config.anarchy ? `/${this.config.anarchy}` : '/an210';
            this.bot.chat(anarCmd);
            await this.delay(3000);

            // Перевод денег (двукратный ввод для FunTime)
            const command = `/pay ${playerName} ${amount}`;
            
            this.bot.chat(command);
            await this.delay(2000);
            this.bot.chat(command);
            await this.delay(3000);
            
            return true;
            
        } catch (error) {
            throw error;
        }
    }

    async disconnect() {
        if (this.bot && this.isConnected) {
            this.bot.quit();
            this.isConnected = false;
            await this.delay(1000);
        }
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Простая функция для выдачи денег
async function payPlayer(playerName, amount) {
    const bot = new SimpleFuntimeBot();
    
    try {
        await bot.connect();
        await bot.giveMoney(playerName, amount);
        
        console.log(JSON.stringify({
            success: true,
            player: playerName,
            amount: amount,
            message: `Successfully transferred ${amount.toLocaleString()} coins to ${playerName}`
        }));
        
        return true;
        
    } catch (error) {
        console.log(JSON.stringify({
            success: false,
            error: error.name || 'unknown_error',
            message: error.message
        }));
        
        return false;
        
    } finally {
        await bot.disconnect();
    }
}

// Простая функция для проверки подключения
async function testConnection() {
    const bot = new SimpleFuntimeBot();
    
    try {
        await bot.connect();
        
        console.log(JSON.stringify({
            success: true,
            isConnected: bot.isConnected,
            message: 'Bot connection test successful'
        }));
        
        return true;
        
    } catch (error) {
        console.log(JSON.stringify({
            success: false,
            isConnected: false,
            error: error.name || 'connection_error',
            message: error.message
        }));
        
        return false;
        
    } finally {
        await bot.disconnect();
    }
}

// Экспорт функций
module.exports = { SimpleFuntimeBot, payPlayer, testConnection };

// Если запущен напрямую
if (require.main === module) {
    const args = process.argv.slice(2);
    
    if (args.length === 0) {
        console.log(JSON.stringify({
            success: false,
            error: 'no_command',
            message: 'Usage: node simple_bot.js <player> <amount> or node simple_bot.js test'
        }));
        process.exit(1);
    }
    
    // Команда тестирования
    if (args[0].toLowerCase() === 'test') {
        // Optional overrides: anarchy, retryIntervalSec, maxAttempts
        if (args[1]) {
            SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { anarchy: args[1] });
        }
        if (args[2]) {
            const retrySec = parseInt(args[2]);
            if (!isNaN(retrySec) && retrySec > 0) SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { retryIntervalMs: retrySec * 1000 });
        }
        if (args[3]) {
            const maxA = parseInt(args[3]);
            if (!isNaN(maxA) && maxA > 0) SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { maxPayAttempts: maxA });
        }

        testConnection().then(success => {
            process.exit(success ? 0 : 1);
        });
        return;
    }
    
    // Команда выдачи денег
    if (args.length < 2) {
        console.log(JSON.stringify({
            success: false,
            error: 'invalid_args',
            message: 'Usage: node simple_bot.js <player> <amount>'
        }));
        process.exit(1);
    }
    
    const playerName = args[0];
    const amount = parseInt(args[1]);
    
    if (isNaN(amount) || amount <= 0) {
        console.log(JSON.stringify({
            success: false,
            error: 'invalid_amount',
            message: 'Invalid amount'
        }));
        process.exit(1);
    }
    
    // Accept two invocation styles:
    // 1) Legacy full: node simple_bot.js <player> <amount> <bot_username> <bot_password> <host> <port> <anarchy>
    // 2) New positional: node simple_bot.js <player> <amount> [anarchy] [retrySec] [maxAttempts] [username] [password] [host] [port]
    if (args.length >= 7 && typeof args[6] === 'string' && args[6].startsWith('an')) {
        // Legacy full format
        SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, {
            username: args[2],
            password: args[3],
            host: args[4],
            port: parseInt(args[5]) || SimpleFuntimeBot.prototype.config.port,
            anarchy: args[6]
        });
    } else {
        // New positional overrides
        if (args[2]) {
            SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { anarchy: args[2] });
        }
        if (args[3]) {
            const retrySec = parseInt(args[3]);
            if (!isNaN(retrySec) && retrySec > 0) SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { retryIntervalMs: retrySec * 1000 });
        }
        if (args[4]) {
            const maxA = parseInt(args[4]);
            if (!isNaN(maxA) && maxA > 0) SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { maxPayAttempts: maxA });
        }
        if (args[5]) {
            SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { username: args[5] });
        }
        if (args[6]) {
            SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { password: args[6] });
        }
        if (args[7]) {
            SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { host: args[7] });
        }
        if (args[8]) {
            const p = parseInt(args[8]);
            if (!isNaN(p) && p > 0) SimpleFuntimeBot.prototype.config = Object.assign(SimpleFuntimeBot.prototype.config || {}, { port: p });
        }
    }

    // Log applied config (password unmasked by user request)
    const applied = Object.assign({}, SimpleFuntimeBot.prototype.config);
    console.error(JSON.stringify({ info: 'applied_config', config: applied }));

    payPlayer(playerName, amount).then(success => {
        process.exit(success ? 0 : 1);
    });
}
