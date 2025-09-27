// src/debug-imports.js
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import VehiclesPassing from './pages/VehiclesPassing';
import CongestedRoads from './pages/CongestedRoads';
import Settings from './pages/Settings';

console.log('Sidebar:', Sidebar);
console.log('Home:', Home);
console.log('VehiclesPassing:', VehiclesPassing);
console.log('CongestedRoads:', CongestedRoads);
console.log('Settings:', Settings);

// Check if they are functions/classes (should be)
console.log('Sidebar type:', typeof Sidebar);
console.log('Home type:', typeof Home);