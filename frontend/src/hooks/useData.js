// src/hooks/useData.js
import { useState, useEffect } from 'react';
import axios from 'axios';

export const useData = (dataTypes = []) => {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        const promises = dataTypes.map(async (type) => {
          switch (type) {
            case 'locations':
              return axios.get('http://127.0.0.1:8000/api/locations/');
            case 'sessions':
              return axios.get('http://127.0.0.1:8000/api/sessions/');
            case 'profiles':
              return axios.get('http://127.0.0.1:8000/api/processing-profiles/');
            default:
              return null;
          }
        });

        const results = await Promise.all(promises);
        
        const newData = {};
        dataTypes.forEach((type, index) => {
          if (results[index]) {
            newData[type] = results[index].data;
          }
        });
        
        setData(newData);
        setError(null);
      } catch (err) {
        setError('Failed to load data');
        console.error('Data loading error:', err);
      } finally {
        setLoading(false);
      }
    };

    if (dataTypes.length > 0) {
      fetchData();
    }
  }, [dataTypes.join(',')]); // Only refetch when dataTypes change

  return { ...data, loading, error };
};