// fix-api-urls.js
const fs = require('fs');
const path = require('path');

const filesToFix = [
  'src/components/LoginModal.js',
  'src/components/VideoUploadModal.js',
  'src/components/EditVideoModal.js',
  'src/components/ProcessedVideoViewer.js',
  'src/pages/LocationsList.js',
  'src/pages/LocationGroups.js',
  'src/pages/GroupVideos.js',
  'src/pages/VehiclesPassing.js',
  'src/pages/CongestedRoads.js',
  'src/pages/Home.js',
  'src/pages/TrafficPredictions.js',
  'src/pages/Settings.js',
];

const replacements = [
  {
    from: 'http://127.0.0.1:8000/api/',
    to: `\${API_CONFIG.BASE_URL}/api/`
  },
  {
    from: "'http://127.0.0.1:8000",
    to: "`${API_CONFIG.BASE_URL}"
  },
  {
    from: '"http://127.0.0.1:8000',
    to: '`${API_CONFIG.BASE_URL}'
  }
];

filesToFix.forEach(filePath => {
  const fullPath = path.join(__dirname, filePath);
  
  if (!fs.existsSync(fullPath)) {
    console.log(`❌ File not found: ${filePath}`);
    return;
  }
  
  let content = fs.readFileSync(fullPath, 'utf8');
  let changed = false;
  
  // Add import at top if not present
  if (!content.includes("import API_CONFIG")) {
    const importLine = "import API_CONFIG from '../config/api';\n";
    const firstImportIndex = content.indexOf('import');
    if (firstImportIndex !== -1) {
      content = content.slice(0, firstImportIndex) + importLine + content.slice(firstImportIndex);
      changed = true;
    }
  }
  
  // Replace all localhost URLs
  replacements.forEach(({ from, to }) => {
    if (content.includes(from)) {
      content = content.split(from).join(to);
      changed = true;
    }
  });
  
  if (changed) {
    fs.writeFileSync(fullPath, content, 'utf8');
    console.log(`✅ Fixed: ${filePath}`);
  } else {
    console.log(`ℹ️  No changes needed: ${filePath}`);
  }
});

console.log('\n✅ Done! All API URLs updated.');