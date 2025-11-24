<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
    <div class="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b">
        <h2 class="text-xl font-semibold">Sync Projects with Datalakes</h2>
        <button @click="close" class="text-gray-500 hover:text-gray-700">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Tabs -->
      <div class="flex border-b">
        <button
          v-for="tab in tabs"
          :key="tab"
          @click="activeTab = tab"
          :class="[
            'px-6 py-3 font-medium transition-colors',
            activeTab === tab
              ? 'text-[#b26a45] border-b-2 border-[#b26a45]'
              : 'text-gray-600 hover:text-gray-900'
          ]"
        >
          {{ tab }}
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-6">
        <!-- Download Tab -->
        <div v-if="activeTab === 'Download'">
          <div v-if="!datalakes.length" class="text-center text-gray-500 py-8">
            No datalakes configured. Add a datalake in the Manage tab.
          </div>
          <div v-else>
            <!-- Datalake Selection -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">Select Datalake</label>
              <select
                v-model="selectedDatalake"
                @change="loadDatalakeProjects"
                class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
              >
                <option value="">-- Select a datalake --</option>
                <option v-for="dl in datalakes" :key="dl.name" :value="dl.name">
                  {{ dl.name }} ({{ dl.type }})
                </option>
              </select>
            </div>

            <!-- Project Selection -->
            <div v-if="selectedDatalake && uniqueProjects.length > 0" class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">Select Project</label>
              <select
                v-model="selectedProject"
                class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
              >
                <option value="">-- Select a project --</option>
                <option v-for="project in uniqueProjects" :key="project.name" :value="project.name">
                  {{ project.display_name }}
                </option>
              </select>
            </div>

            <!-- Version List -->
            <div v-if="selectedProject && projectVersions.length > 0" class="space-y-2">
              <h3 class="font-medium text-gray-900 mb-3">Available Versions</h3>
              
              <!-- Download Progress (shown when downloading without conflict) -->
              <div v-if="downloading && !showConflictDialog" class="mb-4 p-4 border rounded-lg bg-blue-50">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-sm font-medium text-gray-700">Downloading...</span>
                  <span class="text-sm font-medium text-gray-700">{{ downloadProgress }}%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2.5">
                  <div
                    class="bg-[#b26a45] h-2.5 rounded-full transition-all duration-300"
                    :style="{ width: downloadProgress + '%' }"
                  ></div>
                </div>
              </div>

              <div
                v-for="version in projectVersions"
                :key="version.version"
                class="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50"
              >
                <div class="flex-1">
                  <div class="font-medium">Version {{ version.version }}</div>
                  <div class="text-sm text-gray-600">
                    Database: {{ formatBytes(version.db_size_bytes) }} | 
                    Schema: {{ formatBytes(version.schema_size_bytes) }}
                  </div>
                  <div v-if="version.description" class="text-sm text-gray-500 mt-1">
                    {{ version.description }}
                  </div>
                  <div class="text-xs text-gray-400 mt-1">
                    Last modified: {{ formatDate(version.last_modified) }}
                  </div>
                </div>
                <button
                  @click="initiateDownload(version)"
                  :disabled="downloading"
                  class="ml-4 px-4 py-2 bg-[#b26a45] text-white rounded hover:bg-[#9a5838] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Download
                </button>
              </div>
            </div>

            <div v-else-if="selectedDatalake && loadingProjects" class="text-center text-gray-500 py-8">
              Loading projects...
            </div>

            <div v-else-if="selectedDatalake && datalakeProjects.length === 0" class="text-center text-gray-500 py-8">
              No projects found in this datalake.
            </div>

            <div v-else-if="selectedProject && projectVersions.length === 0" class="text-center text-gray-500 py-8">
              No versions found for this project.
            </div>
          </div>
        </div>

        <!-- Upload Tab -->
        <div v-if="activeTab === 'Upload'">
          <div v-if="!datalakes.length" class="text-center text-gray-500 py-8">
            No datalakes configured. Add a datalake in the Manage tab.
          </div>
          <div v-else>
            <!-- Datalake Selection -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">Select Datalake</label>
              <select
                v-model="uploadDatalake"
                class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
              >
                <option value="">-- Select a datalake --</option>
                <option v-for="dl in datalakes" :key="dl.name" :value="dl.name">
                  {{ dl.name }} ({{ dl.type }})
                </option>
              </select>
            </div>

            <!-- Project Selection -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">Select Project</label>
              <select
                v-model="uploadProject"
                class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
              >
                <option value="">-- Select a project --</option>
                <option v-for="project in localProjects" :key="project.path" :value="project.path">
                  {{ project.subdirectory ? `${project.subdirectory}/` : '' }}{{ project.display_name }}{{ project.version ? ` (v${project.version})` : '' }}
                </option>
              </select>
            </div>

            <!-- Version Input -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                New Version (optional)
                <span class="text-sm text-gray-500 font-normal">
                  - Leave empty to use current version
                </span>
              </label>
              <input
                v-model="uploadVersion"
                type="text"
                placeholder="e.g., 1.1.0"
                class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
              />
            </div>

            <!-- Schema Only Checkbox -->
            <div class="mb-4 flex items-center">
              <input
                v-model="uploadSchemaOnly"
                type="checkbox"
                id="schemaOnly"
                class="h-4 w-4 text-[#b26a45] focus:ring-[#b26a45] border-gray-300 rounded"
              />
              <label for="schemaOnly" class="ml-2 block text-sm text-gray-900">
                Upload schema only (skip database file)
              </label>
            </div>

            <!-- Upload Button -->
            <button
              @click="handleUpload"
              :disabled="!uploadDatalake || !uploadProject || uploading"
              class="w-full px-4 py-2 bg-[#b26a45] text-white rounded hover:bg-[#9a5838] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              <svg v-if="uploading" class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>{{ uploading ? 'Uploading...' : 'Upload Project' }}</span>
            </button>

            <!-- Progress Bar -->
            <div v-if="uploading" class="mt-4">
              <div class="flex justify-between text-sm text-gray-600 mb-1">
                <span>Upload progress</span>
                <span>{{ uploadProgress }}%</span>
              </div>
              <div class="w-full bg-gray-200 rounded-full h-2.5">
                <div
                  class="bg-[#b26a45] h-2.5 rounded-full transition-all duration-300"
                  :style="{ width: uploadProgress + '%' }"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Manage Tab -->
        <div v-if="activeTab === 'Manage'">
          <!-- Add Datalake -->
          <div class="mb-6 p-4 border rounded-lg">
            <h3 class="font-medium text-gray-900 mb-4">Add New Datalake</h3>
            <div class="space-y-3">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  v-model="newDatalake.name"
                  type="text"
                  placeholder="e.g., production"
                  class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Storage Type</label>
                <select
                  v-model="newDatalake.type"
                  class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
                >
                  <option value="azure_storage">Azure Storage</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Connection String</label>
                <input
                  v-model="newDatalake.connection_string"
                  type="password"
                  placeholder="Azure Storage connection string"
                  class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
                />
              </div>
              <div v-if="newDatalake.connection_string">
                <button
                  @click="handleTestConnection"
                  :disabled="testingConnection || !newDatalake.connection_string"
                  class="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <svg v-if="testingConnection" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>{{ testingConnection ? 'Testing...' : 'Test Connection' }}</span>
                </button>
                <div v-if="connectionTestMessage" :class="[
                  'mt-2 p-2 rounded text-sm',
                  connectionTestSuccess ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                ]">
                  {{ connectionTestMessage }}
                </div>
              </div>
              <div v-if="availableContainers.length > 0">
                <label class="block text-sm font-medium text-gray-700 mb-1">Container Name</label>
                <select
                  v-model="newDatalake.container_name"
                  class="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-[#b26a45]"
                >
                  <option value="" disabled>-- Select a container --</option>
                  <option v-for="container in availableContainers" :key="container" :value="container">
                    {{ container }}
                  </option>
                </select>
              </div>
              <button
                @click="handleAddDatalake"
                :disabled="!newDatalake.name || !newDatalake.connection_string || !newDatalake.container_name || !connectionTestSuccess"
                class="w-full px-4 py-2 bg-[#b26a45] text-white rounded hover:bg-[#9a5838] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Add Datalake
              </button>
            </div>
          </div>

          <!-- Existing Datalakes -->
          <div>
            <h3 class="font-medium text-gray-900 mb-3">Configured Datalakes</h3>
            <div v-if="!datalakes.length" class="text-center text-gray-500 py-4">
              No datalakes configured yet.
            </div>
            <div v-else class="space-y-2">
              <div
                v-for="dl in datalakes"
                :key="dl.name"
                class="flex items-center justify-between p-3 border rounded-lg"
              >
                <div class="flex-1">
                  <div class="font-medium">{{ dl.name }}</div>
                  <div class="text-sm text-gray-600">
                    Type: {{ formatStorageType(dl.type) }}
                  </div>
                  <div class="text-sm text-gray-600">
                    Storage Account: {{ dl.storage_account }}
                  </div>
                  <div class="text-sm text-gray-600">
                    Container: {{ dl.container_name }}
                  </div>
                </div>
                <button
                  @click="handleDeleteDatalake(dl.name)"
                  class="px-3 py-1 text-red-600 hover:bg-red-50 rounded transition-colors"
                >
                  Remove
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Status Message -->
      <div v-if="statusMessage" class="px-6 py-3 border-t">
        <div
          :class="[
            'p-3 rounded',
            statusType === 'error' ? 'bg-red-50 text-red-800' : 'bg-green-50 text-green-800'
          ]"
        >
          {{ statusMessage }}
        </div>
      </div>
    </div>

    <!-- Conflict Resolution Dialog -->
    <div
      v-if="showConflictDialog"
      class="fixed inset-0 z-60 flex items-center justify-center bg-black/50"
    >
      <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-semibold mb-4">File Conflict</h3>
        <p class="text-gray-700 mb-6">
          Project "{{ conflictProject?.display_name }}" already exists locally. How would you like to proceed?
        </p>
        
        <!-- Download Progress -->
        <div v-if="downloading" class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-gray-700">Downloading...</span>
            <span class="text-sm font-medium text-gray-700">{{ downloadProgress }}%</span>
          </div>
          <div class="w-full bg-gray-200 rounded-full h-2.5">
            <div
              class="bg-[#b26a45] h-2.5 rounded-full transition-all duration-300"
              :style="{ width: downloadProgress + '%' }"
            ></div>
          </div>
        </div>

        <div class="flex gap-3">
          <button
            @click="resolveConflict('overwrite')"
            :disabled="downloading"
            class="flex-1 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Overwrite
          </button>
          <button
            @click="resolveConflict('keep-both')"
            :disabled="downloading"
            class="flex-1 px-4 py-2 bg-[#b26a45] text-white rounded hover:bg-[#9a5838] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Keep Both
          </button>
          <button
            @click="showConflictDialog = false"
            :disabled="downloading"
            class="flex-1 px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import {
    addDatalake,
    deleteDatalake,
    downloadProject,
    fetchDatalakeProjects,
    fetchDatalakes,
    fetchProjects,
    testDatalakeConnection,
    uploadProject as uploadProjectToServer,
} from '../api/client';
import { useSessionStore } from '../stores/session';
import type {
    DatalakeInfo,
    DatalakeProjectInfo,
    ProjectInfo
} from '../types/api';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'refresh'): void;
}>();

const sessionStore = useSessionStore();

const tabs = ['Download', 'Upload', 'Manage'];
const activeTab = ref('Download');

// Datalakes
const datalakes = ref<DatalakeInfo[]>([]);

// Download tab
const selectedDatalake = ref('');
const selectedProject = ref('');
const datalakeProjects = ref<DatalakeProjectInfo[]>([]);
const loadingProjects = ref(false);
const showConflictDialog = ref(false);
const conflictProject = ref<DatalakeProjectInfo | null>(null);
const downloading = ref(false);
const downloadProgress = ref(0);

// Upload tab
const uploadDatalake = ref('');
const uploadProject = ref('');
const uploadVersion = ref('');
const uploadSchemaOnly = ref(false);
const localProjects = ref<ProjectInfo[]>([]);
const uploading = ref(false);
const uploadProgress = ref(0);

// Manage tab
const newDatalake = ref({
  name: '',
  type: 'azure_storage',
  connection_string: '',
  container_name: '',
});
const testingConnection = ref(false);
const connectionTestSuccess = ref(false);
const connectionTestMessage = ref('');
const availableContainers = ref<string[]>([]);

// Status
const statusMessage = ref('');
const statusType = ref<'success' | 'error'>('success');
const statusTimeout = ref<number | null>(null);

function close() {
  emit('close');
}

// Computed properties for project filtering
const uniqueProjects = computed(() => {
  const projectMap = new Map<string, { name: string; display_name: string }>();
  for (const project of datalakeProjects.value) {
    if (!projectMap.has(project.name)) {
      projectMap.set(project.name, {
        name: project.name,
        display_name: project.display_name,
      });
    }
  }
  return Array.from(projectMap.values()).sort((a, b) => 
    a.display_name.localeCompare(b.display_name)
  );
});

const projectVersions = computed(() => {
  if (!selectedProject.value) return [];
  return datalakeProjects.value
    .filter(p => p.name === selectedProject.value)
    .sort((a, b) => b.version.localeCompare(a.version)); // Sort versions descending
});

function formatBytes(bytes: number | undefined): string {
  if (bytes === undefined || bytes === null || isNaN(bytes)) return '0 Bytes';
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleString();
  } catch {
    return dateString;
  }
}

function formatStorageType(type: string): string {
  if (type === 'azure_storage') return 'Azure Storage';
  return type;
}

async function loadDatalakes() {
  try {
    datalakes.value = await fetchDatalakes();
  } catch (error) {
    showStatus(`Failed to load datalakes: ${error}`, 'error');
  }
}

async function loadDatalakeProjects() {
  if (!selectedDatalake.value) return;

  loadingProjects.value = true;
  try {
    datalakeProjects.value = await fetchDatalakeProjects(selectedDatalake.value);
  } catch (error) {
    showStatus(`Failed to load projects: ${error}`, 'error');
  } finally {
    loadingProjects.value = false;
  }
}

async function loadLocalProjects() {
  try {
    localProjects.value = await fetchProjects();
    // Pre-select current project when projects are loaded
    preSelectCurrentProject();
  } catch (error) {
    showStatus(`Failed to load local projects: ${error}`, 'error');
  }
}

function preSelectCurrentProject() {
  // Always update to current project when called
  if (sessionStore.activeProjectInfo) {
    const currentProjectPath = sessionStore.activeProjectInfo.path;
    const exists = localProjects.value.find(p => p.path === currentProjectPath);
    if (exists) {
      uploadProject.value = currentProjectPath;
    }
  }
}

async function initiateDownload(project: DatalakeProjectInfo) {
  // Check if project exists locally
  const existsLocally = localProjects.value.some(p => p.name === project.name);
  
  if (existsLocally) {
    // Show conflict dialog if project exists
    conflictProject.value = project;
    showConflictDialog.value = true;
  } else {
    // Download directly without conflict dialog
    await downloadDirectly(project);
  }
}

async function downloadDirectly(project: DatalakeProjectInfo) {
  if (!selectedDatalake.value) return;

  downloading.value = true;
  downloadProgress.value = 0;

  // Simulate progress with a gradual increase
  const progressInterval = setInterval(() => {
    if (downloadProgress.value < 70) {
      downloadProgress.value += 5;
    } else if (downloadProgress.value < 85) {
      downloadProgress.value += 2;
    } else if (downloadProgress.value < 95) {
      downloadProgress.value += 1;
    }
  }, 300);

  try {
    const response = await downloadProject({
      datalake_name: selectedDatalake.value,
      project_name: project.name,
      version: project.version,
      overwrite: false,
      rename_existing: false,
    });

    downloadProgress.value = 100;
    showStatus(response.message || 'Project downloaded successfully', 'success');
    emit('refresh');
  } catch (error: any) {
    showStatus(`Download failed: ${error.response?.data?.detail || error.message}`, 'error');
  } finally {
    clearInterval(progressInterval);
    setTimeout(() => {
      downloading.value = false;
      downloadProgress.value = 0;
    }, 500);
  }
}

async function resolveConflict(resolution: 'overwrite' | 'keep-both') {
  if (!conflictProject.value || !selectedDatalake.value) return;

  downloading.value = true;
  downloadProgress.value = 0;

  // Simulate progress with a gradual increase
  const progressInterval = setInterval(() => {
    if (downloadProgress.value < 70) {
      downloadProgress.value += 5;
    } else if (downloadProgress.value < 85) {
      downloadProgress.value += 2;
    } else if (downloadProgress.value < 95) {
      downloadProgress.value += 1;
    }
  }, 300);

  try {
    const response = await downloadProject({
      datalake_name: selectedDatalake.value,
      project_name: conflictProject.value.name,
      version: conflictProject.value.version,
      overwrite: resolution === 'overwrite',
      rename_existing: resolution === 'keep-both',
    });

    downloadProgress.value = 100;
    showStatus(response.message || 'Project downloaded successfully', 'success');
    emit('refresh');
  } catch (error: any) {
    showStatus(`Download failed: ${error.response?.data?.detail || error.message}`, 'error');
  } finally {
    clearInterval(progressInterval);
    setTimeout(() => {
      downloading.value = false;
      downloadProgress.value = 0;
      showConflictDialog.value = false;
    }, 500);
  }
}

async function handleUpload() {
  if (!uploadDatalake.value || !uploadProject.value || uploading.value) return;

  // Get project info for display
  const projectInfo = localProjects.value.find(p => p.path === uploadProject.value);
  const projectDisplayName = projectInfo?.display_name || 'project';
  const projectName = projectInfo?.name || 'project';
  
  // Determine the version that will be used
  let targetVersion = uploadVersion.value || projectInfo?.version || '1.0.0';
  const versionText = uploadVersion.value ? ` (v${uploadVersion.value})` : '';

  // Check if this version already exists in the datalake
  await loadDatalakeProjectsIfNeeded();
  const existingProject = datalakeProjects.value.find(
    p => p.name === projectName && p.version === targetVersion
  );

  // Only show overwrite warning if version already exists
  if (existingProject) {
    const confirmMessage = `A version ${targetVersion} of "${projectDisplayName}" already exists in datalake "${uploadDatalake.value}".\n\nDo you want to overwrite it?`;
    if (!confirm(confirmMessage)) {
      return;
    }
  } else {
    // Simple confirmation for new version
    const confirmMessage = `Upload "${projectDisplayName}"${versionText} to datalake "${uploadDatalake.value}"?`;
    if (!confirm(confirmMessage)) {
      return;
    }
  }

  uploading.value = true;
  uploadProgress.value = 0;
  
  // Simulate progress with a more realistic gradual increase
  // Slows down as it approaches completion to avoid getting stuck at 90%
  const progressInterval = setInterval(() => {
    if (uploadProgress.value < 70) {
      // Fast progress at the beginning
      uploadProgress.value += 5;
    } else if (uploadProgress.value < 85) {
      // Slower in the middle
      uploadProgress.value += 2;
    } else if (uploadProgress.value < 95) {
      // Very slow near the end
      uploadProgress.value += 1;
    }
    // Stop at 95% and let the actual completion set it to 100%
  }, 300);

  try {
    const response = await uploadProjectToServer({
      datalake_name: uploadDatalake.value,
      project_path: uploadProject.value,
      new_version: uploadVersion.value || null,
      schema_only: uploadSchemaOnly.value,
    });

    uploadProgress.value = 100;
    showStatus(response.message || `Project "${projectDisplayName}" uploaded successfully!`, 'success', false);
    uploadVersion.value = '';
    uploadSchemaOnly.value = false;
    
    // Refresh the datalake projects list to show the new/updated version
    if (selectedDatalake.value === uploadDatalake.value) {
      await loadDatalakeProjects();
    }
    
    // Keep the project selected for easy re-upload with different version
    // uploadProject.value = '';
  } catch (error: any) {
    const errorDetail = error.response?.data?.detail || error.message;
    showStatus(`Upload failed: ${errorDetail}`, 'error', false);
  } finally {
    clearInterval(progressInterval);
    setTimeout(() => {
      uploading.value = false;
      uploadProgress.value = 0;
    }, 500);
  }
}

async function loadDatalakeProjectsIfNeeded() {
  // Load projects from the selected upload datalake if not already loaded
  if (uploadDatalake.value && selectedDatalake.value !== uploadDatalake.value) {
    const previousDatalake = selectedDatalake.value;
    selectedDatalake.value = uploadDatalake.value;
    await loadDatalakeProjects();
    selectedDatalake.value = previousDatalake;
  }
}

async function handleTestConnection() {
  if (!newDatalake.value.connection_string) return;

  testingConnection.value = true;
  connectionTestSuccess.value = false;
  connectionTestMessage.value = '';
  availableContainers.value = [];

  try {
    const response = await testDatalakeConnection({
      type: newDatalake.value.type,
      connection_string: newDatalake.value.connection_string,
    });

    connectionTestSuccess.value = response.success;
    connectionTestMessage.value = response.message;

    if (response.success && response.containers.length > 0) {
      availableContainers.value = response.containers;
      if (!newDatalake.value.container_name && response.containers.length > 0) {
        newDatalake.value.container_name = response.containers[0];
      }
    }
  } catch (error: any) {
    connectionTestSuccess.value = false;
    connectionTestMessage.value = `Connection test failed: ${error.response?.data?.detail || error.message}`;
  } finally {
    testingConnection.value = false;
  }
}

async function handleAddDatalake() {
  if (!newDatalake.value.name || !newDatalake.value.connection_string || !newDatalake.value.container_name) return;

  try {
    await addDatalake({
      name: newDatalake.value.name,
      type: newDatalake.value.type,
      connection_string: newDatalake.value.connection_string,
      container_name: newDatalake.value.container_name,
    });

    showStatus('Datalake added successfully', 'success');
    newDatalake.value = {
      name: '',
      type: 'azure_storage',
      connection_string: '',
      container_name: '',
    };
    connectionTestSuccess.value = false;
    connectionTestMessage.value = '';
    availableContainers.value = [];
    await loadDatalakes();
  } catch (error: any) {
    showStatus(`Failed to add datalake: ${error.response?.data?.detail || error.message}`, 'error');
  }
}

async function handleDeleteDatalake(name: string) {
  if (!confirm(`Are you sure you want to remove the datalake "${name}"?`)) return;

  try {
    await deleteDatalake(name);
    showStatus('Datalake removed successfully', 'success');
    await loadDatalakes();
  } catch (error: any) {
    showStatus(`Failed to remove datalake: ${error.response?.data?.detail || error.message}`, 'error');
  }
}

function showStatus(message: string, type: 'success' | 'error', autoHide: boolean = true) {
  // Clear existing timeout
  if (statusTimeout.value) {
    clearTimeout(statusTimeout.value);
    statusTimeout.value = null;
  }

  statusMessage.value = message;
  statusType.value = type;
  
  if (autoHide) {
    statusTimeout.value = window.setTimeout(() => {
      statusMessage.value = '';
      statusTimeout.value = null;
    }, 5000);
  }
}

onMounted(async () => {
  await loadDatalakes();
  await loadLocalProjects();
});

// Watch for dialog opening to reset and pre-select current project
watch(() => props.isOpen, (isOpen) => {
  if (isOpen) {
    preSelectCurrentProject();
  }
});

// Watch for tab changes to pre-select current project when switching to Upload tab
watch(activeTab, (newTab) => {
  if (newTab === 'Upload') {
    preSelectCurrentProject();
  }
});

// Watch for datalake changes to reset project selection and auto-select current project
watch(selectedDatalake, (newValue) => {
  selectedProject.value = '';
  
  // If datalake is cleared (empty string), also clear the projects list
  if (!newValue) {
    datalakeProjects.value = [];
    return;
  }
  
  // Auto-select current active project if available, otherwise first project
  setTimeout(() => {
    if (uniqueProjects.value.length > 0) {
      // Try to find the currently active project
      const currentProjectName = sessionStore.activeProjectInfo?.name;
      const matchingProject = uniqueProjects.value.find(p => p.name === currentProjectName);
      
      if (matchingProject) {
        selectedProject.value = matchingProject.name;
      } else {
        // Fallback to first project if current project not found
        selectedProject.value = uniqueProjects.value[0].name;
      }
    }
  }, 100);
});
</script>
