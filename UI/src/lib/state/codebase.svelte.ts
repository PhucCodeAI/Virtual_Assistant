import { API_BASE_URL } from './config';
import type { CodeNode } from './types';

export class CodebaseService {
    path = $state<string>("");
    extensionsInput = $state<string>(".pyc,.md,.txt");
    ignoredFolders = $state<string[]>([]);
    ignoredFiles = $state<string[]>([]);
    tree = $state<CodeNode | null>(null);
    isScanning = $state<boolean>(false);
    collapsedFolders = $state<string[]>([]);

    async scan() {
        if (!this.path.trim()) return;
        this.isScanning = true;
        try {
            const extList = this.extensionsInput.split(',').map(e => e.trim()).filter(e => e);
            const payload = {
                path: this.path,
                extensions: extList,
                folders: $state.snapshot(this.ignoredFolders),
                files: $state.snapshot(this.ignoredFiles)
            };

            const res = await fetch(`${API_BASE_URL}/utils/codebase`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const result = await res.json();
                this.tree = result.codebase;
                this.collapsedFolders = [
                    this.path + '/.venv',
                    this.path + '/node_modules',
                    this.path + '/.git'
                ];
            }
        } catch (error) {
            console.error("Codebase Scan Error: ", error);
        } finally {
            this.isScanning = false;
        }
    }

    toggleCollapse(p: string) {
        const index = this.collapsedFolders.indexOf(p);
        if (index === -1) this.collapsedFolders.push(p);
        else this.collapsedFolders.splice(index, 1);
    }

    isCollapsed(p: string): boolean {
        return this.collapsedFolders.some(folder => p.endsWith(folder) || folder.endsWith(p));
    }

    toggleIgnore(p: string, type: 'file' | 'folder') {
        const targetArray = type === 'folder' ? this.ignoredFolders : this.ignoredFiles;
        const index = targetArray.indexOf(p);
        if (index === -1) targetArray.push(p);
        else targetArray.splice(index, 1);
    }

    isIgnored(p: string, type: 'file' | 'folder'): boolean {
        return type === 'folder' ? this.ignoredFolders.includes(p) : this.ignoredFiles.includes(p);
    }
}