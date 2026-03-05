//src/pages/LandingPage.js
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

function LandingPage({ user, onGetStarted }) {
  const navigate = useNavigate();
  const [isVisible, setIsVisible] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editedContent, setEditedContent] = useState(null);
  const [uploadingImage, setUploadingImage] = useState(null);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const fileInputRefs = useRef({});
  const carouselRef = useRef(null);
  const autoPlayInterval = useRef(null);

  // Initial content state
  const [content, setContent] = useState({
    hero: {
      emoji: "🚗",
      title: "Traffic Monitor",
      subtitle: "Advanced AI-Powered Traffic Analysis System"
    },
    features: [
      {
        title: "Real-Time Traffic Analysis",
        description: "Monitor traffic patterns and congestion levels across multiple locations with advanced AI-powered video analysis.",
        icon: "🚦",
        image: "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1200&q=80"
      },
      {
        title: "Smart Data Visualization",
        description: "View comprehensive traffic reports with interactive charts and graphs that update in real-time.",
        icon: "📊",
        image: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200&q=80"
      },
      {
        title: "Peak Hour Detection",
        description: "Automatically identify morning and evening rush hours to optimize traffic management strategies.",
        icon: "⏰",
        image: "https://images.unsplash.com/photo-1501594907352-04cda38ebc29?w=1200&q=80"
      },
      {
        title: "Historical Insights",
        description: "Access weekly trends and patterns to make data-driven decisions for urban planning.",
        icon: "📈",
        image: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&q=80"
      },
      {
        title: "Vehicle Classification",
        description: "Automatically classify vehicles by type including cars, trucks, buses, and motorcycles.",
        icon: "🚙",
        image: "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=1200&q=80"
      },
      {
        title: "Predictive Analytics",
        description: "Forecast future traffic patterns based on historical data and machine learning models.",
        icon: "🔮",
        image: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200&q=80"
      }
    ],
    about: {
      title: "About Us",
      mainText: "We are a dedicated team of developers and data scientists committed to revolutionizing urban traffic management through cutting-edge technology and artificial intelligence.",
      secondaryText: "Our mission is to create smarter cities by providing actionable insights from traffic data, helping urban planners and traffic managers make informed decisions that improve the daily commute for millions of people."
    },
    stats: [
      { number: '1M+', label: 'Vehicles Analyzed' },
      { number: '24/7', label: 'Real-time Monitoring' },
      { number: '99.9%', label: 'Accuracy Rate' },
      { number: '100+', label: 'Locations Tracked' }
    ],
    cta: {
      title: "Ready to Transform Traffic Management?",
      subtitle: "Start analyzing traffic patterns and gain valuable insights with our advanced AI system.",
      buttonText: "Begin Your Journey →"
    }
  });

  const [visibleSections, setVisibleSections] = useState({});
  const sectionRefs = useRef({});

  useEffect(() => {
    setIsVisible(true);
  }, []);

  // Auto-play carousel
  useEffect(() => {
    if (isAutoPlaying) {
      autoPlayInterval.current = setInterval(() => {
        setCurrentSlide(prev => (prev + 1) % content.features.length);
      }, 5000);
    }
    
    return () => {
      if (autoPlayInterval.current) {
        clearInterval(autoPlayInterval.current);
      }
    };
  }, [isAutoPlaying, content.features.length]);

  // Intersection Observer for scroll animations
  useEffect(() => {
    const observerOptions = {
      threshold: 0.2,
      rootMargin: '0px 0px -100px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          setVisibleSections(prev => ({
            ...prev,
            [entry.target.dataset.section]: true
          }));
        }
      });
    }, observerOptions);

    Object.values(sectionRefs.current).forEach(ref => {
      if (ref) observer.observe(ref);
    });

    return () => observer.disconnect();
  }, []);

  const handleGetStarted = () => {
    navigate('/home');
  };

  const handleImageUpload = (featureIndex) => {
    return (event) => {
      const file = event.target.files[0];
      if (file) {
        if (!file.type.startsWith('image/')) {
          alert('Please select an image file (JPG, PNG, etc.)');
          return;
        }

        if (file.size > 10 * 1024 * 1024) {
          alert('Image size should be less than 10MB');
          return;
        }

        setUploadingImage({
          featureIndex,
          fileName: file.name
        });

        const reader = new FileReader();
        reader.onload = (e) => {
          const imageUrl = e.target.result;
          
          const updatedContent = { ...content };
          updatedContent.features[featureIndex].image = imageUrl;
          setContent(updatedContent);
          
          setUploadingImage(null);
          event.target.value = '';
        };
        
        reader.onerror = () => {
          alert('Error reading image file');
          setUploadingImage(null);
          event.target.value = '';
        };
        
        reader.readAsDataURL(file);
      }
    };
  };

  const triggerImagePicker = (featureIndex) => {
    if (fileInputRefs.current[featureIndex]) {
      fileInputRefs.current[featureIndex].click();
    }
  };

  const handleEdit = (section, field, value) => {
    setEditedContent({
      ...editedContent,
      [`${section}.${field}`]: value
    });
  };

  const saveChanges = () => {
    const updatedContent = { ...content };
    
    Object.entries(editedContent || {}).forEach(([key, value]) => {
      const [section, ...fields] = key.split('.');
      let target = updatedContent[section];
      
      for (let i = 0; i < fields.length - 1; i++) {
        target = target[fields[i]];
      }
      target[fields[fields.length - 1]] = value;
    });
    
    setContent(updatedContent);
    setEditedContent(null);
    setIsEditMode(false);
    
    try {
      localStorage.setItem('landingPageContent', JSON.stringify(updatedContent));
      alert('Changes saved successfully! (Saved locally)');
    } catch (error) {
      alert('Changes saved to memory, but could not save to localStorage.');
    }
  };

  const cancelEdit = () => {
    setEditedContent(null);
    setIsEditMode(false);
  };

  const getEditedValue = (section, field) => {
    const key = `${section}.${field}`;
    return editedContent?.[key] !== undefined ? editedContent[key] : 
           section.split('.').reduce((obj, k) => obj?.[k], content)?.[field];
  };

  // Carousel controls
  const nextSlide = () => {
    setCurrentSlide(prev => (prev + 1) % content.features.length);
    if (autoPlayInterval.current) {
      clearInterval(autoPlayInterval.current);
      autoPlayInterval.current = null;
    }
  };

  const prevSlide = () => {
    setCurrentSlide(prev => (prev - 1 + content.features.length) % content.features.length);
    if (autoPlayInterval.current) {
      clearInterval(autoPlayInterval.current);
      autoPlayInterval.current = null;
    }
  };

  const goToSlide = (index) => {
    setCurrentSlide(index);
    if (autoPlayInterval.current) {
      clearInterval(autoPlayInterval.current);
      autoPlayInterval.current = null;
    }
  };

  const toggleAutoPlay = () => {
    setIsAutoPlaying(!isAutoPlaying);
  };

  // Load saved content from localStorage
  useEffect(() => {
    try {
      const savedContent = localStorage.getItem('landingPageContent');
      if (savedContent) {
        const parsedContent = JSON.parse(savedContent);
        setContent(parsedContent);
      }
    } catch (error) {
      console.error('Error loading saved content:', error);
    }
  }, []);

  // Calculate slides to show based on screen size
  const getSlidesToShow = () => {
    if (window.innerWidth >= 1200) return 2;
    if (window.innerWidth >= 768) return 1.5;
    return 1;
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#ffffff',
      overflow: 'auto',
      position: 'relative'
    }}>
      {/* Edit Mode Toggle */}
      {user && (
        <div style={{
          position: 'fixed',
          top: '90px',
          right: '20px',
          zIndex: 2000,
          display: 'flex',
          gap: '10px'
        }}>
          {isEditMode ? (
            <>
              <button
                onClick={saveChanges}
                style={{
                  padding: '12px 24px',
                  background: '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: '600',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)'
                }}
              >
                💾 Save Changes
              </button>
              <button
                onClick={cancelEdit}
                style={{
                  padding: '12px 24px',
                  background: '#ef4444',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: '600',
                  boxShadow: '0 4px 12px rgba(239, 68, 68, 0.3)'
                }}
              >
                ✕ Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setIsEditMode(true)}
              style={{
                padding: '12px 24px',
                background: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600',
                boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)'
              }}
            >
              ✏️ Edit Page
            </button>
          )}
        </div>
      )}

      {/* Hidden file inputs */}
      {content.features.map((_, index) => (
        <input
          key={index}
          type="file"
          ref={el => fileInputRefs.current[index] = el}
          style={{ display: 'none' }}
          accept="image/*"
          onChange={handleImageUpload(index)}
        />
      ))}

      {/* Hero Section */}
      <section style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          opacity: 0.1
        }}>
          {[...Array(20)].map((_, i) => (
            <div key={i} style={{
              position: 'absolute',
              width: '2px',
              height: '2px',
              backgroundColor: 'white',
              borderRadius: '50%',
              top: `${Math.random() * 100}%`,
              left: `${Math.random() * 100}%`,
              animation: `twinkle ${2 + Math.random() * 3}s infinite`
            }}></div>
          ))}
        </div>

        <div style={{
          textAlign: 'center',
          padding: '40px 20px',
          maxWidth: '900px',
          transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
          opacity: isVisible ? 1 : 0,
          transition: 'all 1s ease-out',
          position: 'relative',
          zIndex: 1
        }}>
          <div style={{
            fontSize: '72px',
            marginBottom: '20px',
            animation: 'float 3s ease-in-out infinite',
            cursor: isEditMode ? 'pointer' : 'default',
            padding: isEditMode ? '10px' : '0',
            borderRadius: '12px',
            border: isEditMode ? '2px dashed rgba(255,255,255,0.5)' : 'none'
          }}
          onClick={() => isEditMode && handleEdit('hero', 'emoji', prompt('Enter emoji:', content.hero.emoji))}
          >
            {content.hero.emoji}
          </div>
          
          {isEditMode ? (
            <input
              type="text"
              value={getEditedValue('hero', 'title')}
              onChange={(e) => handleEdit('hero', 'title', e.target.value)}
              style={{
                fontSize: '64px',
                fontWeight: '800',
                marginBottom: '24px',
                textShadow: '2px 2px 4px rgba(0,0,0,0.2)',
                letterSpacing: '-1px',
                background: 'rgba(255,255,255,0.2)',
                border: '2px solid white',
                borderRadius: '8px',
                padding: '10px',
                color: 'white',
                textAlign: 'center',
                width: '100%'
              }}
            />
          ) : (
            <h1 style={{
              fontSize: '64px',
              fontWeight: '800',
              marginBottom: '24px',
              textShadow: '2px 2px 4px rgba(0,0,0,0.2)',
              letterSpacing: '-1px'
            }}>
              {content.hero.title}
            </h1>
          )}
          
          {isEditMode ? (
            <input
              type="text"
              value={getEditedValue('hero', 'subtitle')}
              onChange={(e) => handleEdit('hero', 'subtitle', e.target.value)}
              style={{
                fontSize: '24px',
                marginBottom: '48px',
                background: 'rgba(255,255,255,0.2)',
                border: '2px solid white',
                borderRadius: '8px',
                padding: '10px',
                color: 'white',
                textAlign: 'center',
                width: '100%'
              }}
            />
          ) : (
            <p style={{
              fontSize: '24px',
              marginBottom: '48px',
              opacity: 0.95,
              lineHeight: '1.6',
              fontWeight: '300'
            }}>
              {content.hero.subtitle}
            </p>
          )}
          
          <button
            onClick={handleGetStarted}
            style={{
              padding: '18px 48px',
              fontSize: '20px',
              fontWeight: '600',
              color: '#667eea',
              backgroundColor: 'white',
              border: 'none',
              borderRadius: '50px',
              cursor: 'pointer',
              boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
              transition: 'all 0.3s ease',
              transform: 'scale(1)'
            }}
            onMouseEnter={(e) => {
              e.target.style.transform = 'scale(1.05) translateY(-2px)';
              e.target.style.boxShadow = '0 15px 40px rgba(0,0,0,0.4)';
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = 'scale(1) translateY(0)';
              e.target.style.boxShadow = '0 10px 30px rgba(0,0,0,0.3)';
            }}
          >
            Get Started →
          </button>
          
          <div style={{
            marginTop: '80px',
            animation: 'bounce 2s infinite'
          }}>
            <div style={{
              fontSize: '14px',
              opacity: 0.8,
              marginBottom: '8px',
              fontWeight: '500'
            }}>
              Scroll to explore
            </div>
            <div style={{
              fontSize: '24px',
              opacity: 0.8
            }}>↓</div>
          </div>
        </div>
      </section>

      {/* Features Carousel Section */}
      <section 
        ref={el => sectionRefs.current['features'] = el}
        data-section="features"
        style={{
          minHeight: '90vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#f7fafc',
          padding: '60px 20px',
          position: 'relative'
        }}
      >
        <div style={{
          maxWidth: '1400px',
          width: '100%',
          margin: '0 auto'
        }}>
          <div style={{
            textAlign: 'center',
            marginBottom: '40px'
          }}>
            <h2 style={{
              fontSize: '48px',
              fontWeight: '700',
              marginBottom: '20px',
              color: '#2d3748',
              opacity: visibleSections['features'] ? 1 : 0,
              transform: visibleSections['features'] ? 'translateY(0)' : 'translateY(30px)',
              transition: 'all 0.8s ease'
            }}>
              Powerful Features
            </h2>
            <p style={{
              fontSize: '20px',
              color: '#718096',
              maxWidth: '800px',
              margin: '0 auto',
              lineHeight: '1.6'
            }}>
              Explore our comprehensive suite of traffic analysis tools designed to revolutionize urban mobility
            </p>
          </div>

          {/* Carousel Container */}
          <div style={{
            position: 'relative',
            margin: '40px 0',
            overflow: 'hidden'
          }}>
            {/* Carousel Controls */}
            <div style={{
              position: 'absolute',
              top: '50%',
              left: '0',
              right: '0',
              transform: 'translateY(-50%)',
              display: 'flex',
              justifyContent: 'space-between',
              padding: '0 20px',
              zIndex: 10
            }}>
              <button
                onClick={prevSlide}
                style={{
                  width: '50px',
                  height: '50px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(255, 255, 255, 0.9)',
                  border: 'none',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '20px',
                  color: '#2d3748',
                  transition: 'all 0.3s ease',
                  zIndex: 10
                }}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = 'white';
                  e.target.style.transform = 'scale(1.1)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
                  e.target.style.transform = 'scale(1)';
                }}
              >
                ◀
              </button>
              <button
                onClick={nextSlide}
                style={{
                  width: '50px',
                  height: '50px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(255, 255, 255, 0.9)',
                  border: 'none',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '20px',
                  color: '#2d3748',
                  transition: 'all 0.3s ease',
                  zIndex: 10
                }}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = 'white';
                  e.target.style.transform = 'scale(1.1)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
                  e.target.style.transform = 'scale(1)';
                }}
              >
                ▶
              </button>
            </div>

            {/* Auto-play toggle */}
            <div style={{
              position: 'absolute',
              top: '20px',
              right: '20px',
              zIndex: 10
            }}>
              <button
                onClick={toggleAutoPlay}
                style={{
                  padding: '8px 16px',
                  backgroundColor: 'rgba(255, 255, 255, 0.9)',
                  border: 'none',
                  borderRadius: '20px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  color: '#2d3748',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
                  transition: 'all 0.3s ease'
                }}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = 'white';
                  e.target.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.15)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
                  e.target.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.1)';
                }}
              >
                {isAutoPlaying ? '⏸️ Pause' : '▶️ Play'}
              </button>
            </div>

            {/* Carousel Track */}
            <div
              ref={carouselRef}
              style={{
                display: 'flex',
                transition: 'transform 0.5s ease-in-out',
                transform: `translateX(-${currentSlide * (100 / getSlidesToShow())}%)`,
                width: `${content.features.length * (100 / getSlidesToShow())}%`
              }}
            >
              {content.features.map((feature, index) => (
                <div
                  key={index}
                  style={{
                    flex: `0 0 ${100 / getSlidesToShow()}%`,
                    padding: '0 20px',
                    boxSizing: 'border-box'
                  }}
                >
                  <div style={{
                    backgroundColor: 'white',
                    borderRadius: '20px',
                    overflow: 'hidden',
                    boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1)',
                    height: '600px',
                    position: 'relative',
                    transition: 'all 0.3s ease',
                    transform: currentSlide === index ? 'scale(1.02)' : 'scale(0.98)',
                    opacity: currentSlide === index ? 1 : 0.9
                  }}>
                    {/* Feature Image */}
                    <div style={{
                      position: 'relative',
                      height: '400px',
                      overflow: 'hidden',
                      cursor: isEditMode ? 'pointer' : 'default'
                    }}
                    onClick={() => isEditMode && triggerImagePicker(index)}
                    >
                      {uploadingImage?.featureIndex === index ? (
                        <div style={{
                          width: '100%',
                          height: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          backgroundColor: '#f3f4f6'
                        }}>
                          <div style={{
                            textAlign: 'center',
                            color: '#6b7280'
                          }}>
                            <div style={{
                              marginBottom: '12px',
                              fontSize: '32px',
                              animation: 'spin 1s linear infinite'
                            }}>
                            ⏳
                            </div>
                            <div style={{
                              fontSize: '14px',
                              maxWidth: '80%',
                              margin: '0 auto'
                            }}>
                              Uploading {uploadingImage.fileName}...
                            </div>
                          </div>
                        </div>
                      ) : (
                        <>
                          <img 
                            src={feature.image}
                            alt={feature.title}
                            style={{
                              width: '100%',
                              height: '100%',
                              objectFit: 'cover',
                              transition: 'transform 0.5s ease'
                            }}
                          />
                          {isEditMode && !uploadingImage && (
                            <div style={{
                              position: 'absolute',
                              top: '0',
                              left: '0',
                              right: '0',
                              bottom: '0',
                              backgroundColor: 'rgba(0, 0, 0, 0.7)',
                              display: 'flex',
                              flexDirection: 'column',
                              alignItems: 'center',
                              justifyContent: 'center',
                              opacity: 0,
                              transition: 'opacity 0.3s ease',
                              color: 'white',
                              fontSize: '16px',
                              textAlign: 'center',
                              padding: '30px'
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.opacity = 1}
                            onMouseLeave={(e) => e.currentTarget.style.opacity = 0}
                            >
                              <div style={{
                                fontSize: '36px',
                                marginBottom: '12px'
                              }}>
                                📁
                              </div>
                              Click to upload new image
                              <div style={{
                                fontSize: '14px',
                                opacity: 0.8,
                                marginTop: '8px',
                                maxWidth: '300px'
                              }}>
                                JPG, PNG up to 10MB recommended
                              </div>
                            </div>
                          )}
                        </>
                      )}
                      <div style={{
                        position: 'absolute',
                        top: '20px',
                        left: '20px',
                        fontSize: '48px',
                        background: 'rgba(255, 255, 255, 0.95)',
                        padding: '12px 16px',
                        borderRadius: '12px',
                        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                        zIndex: 2
                      }}>
                        {feature.icon}
                      </div>
                    </div>

                    {/* Feature Content */}
                    <div style={{ 
                      padding: '30px',
                      height: '200px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center'
                    }}>
                      {isEditMode ? (
                        <input
                          type="text"
                          value={getEditedValue('features', `${index}.title`)}
                          onChange={(e) => handleEdit('features', `${index}.title`, e.target.value)}
                          style={{
                            width: '100%',
                            fontSize: '24px',
                            fontWeight: '700',
                            marginBottom: '16px',
                            padding: '12px',
                            border: '2px solid #3b82f6',
                            borderRadius: '8px',
                            backgroundColor: '#f8fafc'
                          }}
                        />
                      ) : (
                        <h3 style={{
                          fontSize: '24px',
                          fontWeight: '700',
                          marginBottom: '16px',
                          color: '#2d3748',
                          lineHeight: '1.3'
                        }}>
                          {feature.title}
                        </h3>
                      )}
                      {isEditMode ? (
                        <textarea
                          value={getEditedValue('features', `${index}.description`)}
                          onChange={(e) => handleEdit('features', `${index}.description`, e.target.value)}
                          style={{
                            width: '100%',
                            fontSize: '16px',
                            color: '#718096',
                            lineHeight: '1.6',
                            padding: '12px',
                            border: '2px solid #3b82f6',
                            borderRadius: '8px',
                            minHeight: '100px',
                            resize: 'vertical',
                            backgroundColor: '#f8fafc'
                          }}
                        />
                      ) : (
                        <p style={{
                          fontSize: '16px',
                          color: '#718096',
                          lineHeight: '1.6',
                          margin: 0
                        }}>
                          {feature.description}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Dots Navigation */}
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              marginTop: '40px',
              gap: '12px',
              flexWrap: 'wrap'
            }}>
              {content.features.map((_, index) => (
                <button
                  key={index}
                  onClick={() => goToSlide(index)}
                  style={{
                    width: currentSlide === index ? '24px' : '12px',
                    height: '12px',
                    borderRadius: '6px',
                    backgroundColor: currentSlide === index ? '#3b82f6' : '#cbd5e1',
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease',
                    padding: 0
                  }}
                  onMouseEnter={(e) => {
                    if (currentSlide !== index) {
                      e.target.style.backgroundColor = '#94a3b8';
                      e.target.style.width = '18px';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (currentSlide !== index) {
                      e.target.style.backgroundColor = '#cbd5e1';
                      e.target.style.width = '12px';
                    }
                  }}
                />
              ))}
            </div>

            {/* Slide Counter */}
            <div style={{
              textAlign: 'center',
              marginTop: '20px',
              fontSize: '14px',
              color: '#6b7280',
              fontWeight: '500'
            }}>
              {currentSlide + 1} / {content.features.length}
            </div>
          </div>

          {/* Feature Summary */}
          <div style={{
            textAlign: 'center',
            marginTop: '60px',
            padding: '40px',
            backgroundColor: 'rgba(59, 130, 246, 0.05)',
            borderRadius: '16px',
            border: '1px solid rgba(59, 130, 246, 0.1)'
          }}>
            <p style={{
              fontSize: '18px',
              color: '#4b5563',
              maxWidth: '800px',
              margin: '0 auto',
              lineHeight: '1.7'
            }}>
              Our platform combines cutting-edge AI technology with intuitive interfaces to provide 
              comprehensive traffic analysis solutions for cities, transportation departments, 
              and urban planners worldwide.
            </p>
          </div>
        </div>
      </section>

      {/* About Us Section */}
      <section
        ref={el => sectionRefs.current['about'] = el}
        data-section="about"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          padding: '80px 20px'
        }}
      >
        <div style={{
          maxWidth: '1200px',
          width: '100%'
        }}>
          {isEditMode ? (
            <input
              type="text"
              value={getEditedValue('about', 'title')}
              onChange={(e) => handleEdit('about', 'title', e.target.value)}
              style={{
                fontSize: '48px',
                fontWeight: '700',
                textAlign: 'center',
                marginBottom: '32px',
                width: '100%',
                background: 'rgba(255,255,255,0.2)',
                border: '2px solid white',
                borderRadius: '8px',
                padding: '10px',
                color: 'white'
              }}
            />
          ) : (
            <h2 style={{
              fontSize: '48px',
              fontWeight: '700',
              textAlign: 'center',
              marginBottom: '32px',
              opacity: visibleSections['about'] ? 1 : 0,
              transform: visibleSections['about'] ? 'scale(1)' : 'scale(0.9)',
              transition: 'all 0.8s ease'
            }}>
              {content.about.title}
            </h2>
          )}
          
          <div style={{
            backgroundColor: 'rgba(255,255,255,0.1)',
            backdropFilter: 'blur(10px)',
            borderRadius: '20px',
            padding: '60px 40px',
            textAlign: 'center',
            marginBottom: '60px',
            opacity: visibleSections['about'] ? 1 : 0,
            transform: visibleSections['about'] ? 'translateY(0)' : 'translateY(30px)',
            transition: 'all 0.8s ease 0.2s'
          }}>
            {isEditMode ? (
              <textarea
                value={getEditedValue('about', 'mainText')}
                onChange={(e) => handleEdit('about', 'mainText', e.target.value)}
                style={{
                  fontSize: '24px',
                  lineHeight: '1.8',
                  maxWidth: '800px',
                  margin: '0 auto 40px',
                  fontWeight: '300',
                  width: '100%',
                  background: 'rgba(255,255,255,0.2)',
                  border: '2px solid white',
                  borderRadius: '8px',
                  padding: '15px',
                  color: 'white',
                  minHeight: '120px',
                  resize: 'vertical'
                }}
              />
            ) : (
              <p style={{
                fontSize: '24px',
                lineHeight: '1.8',
                maxWidth: '800px',
                margin: '0 auto 40px',
                fontWeight: '300'
              }}>
                {content.about.mainText}
              </p>
            )}
            {isEditMode ? (
              <textarea
                value={getEditedValue('about', 'secondaryText')}
                onChange={(e) => handleEdit('about', 'secondaryText', e.target.value)}
                style={{
                  fontSize: '18px',
                  lineHeight: '1.8',
                  maxWidth: '800px',
                  margin: '0 auto',
                  opacity: 0.9,
                  width: '100%',
                  background: 'rgba(255,255,255,0.2)',
                  border: '2px solid white',
                  borderRadius: '8px',
                  padding: '15px',
                  color: 'white',
                  minHeight: '100px',
                  resize: 'vertical'
                }}
              />
            ) : (
              <p style={{
                fontSize: '18px',
                lineHeight: '1.8',
                maxWidth: '800px',
                margin: '0 auto',
                opacity: 0.9
              }}>
                {content.about.secondaryText}
              </p>
            )}
          </div>

          {/* Stats */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '32px',
            marginTop: '60px'
          }}>
            {content.stats.map((stat, index) => (
              <div
                key={index}
                style={{
                  textAlign: 'center',
                  padding: '32px',
                  backgroundColor: 'rgba(255,255,255,0.15)',
                  borderRadius: '12px',
                  backdropFilter: 'blur(10px)',
                  opacity: visibleSections['about'] ? 1 : 0,
                  transform: visibleSections['about'] ? 'translateY(0)' : 'translateY(30px)',
                  transition: 'all 0.6s ease',
                  transitionDelay: `${0.4 + index * 0.1}s`
                }}
              >
                {isEditMode ? (
                  <input
                    type="text"
                    value={getEditedValue('stats', `${index}.number`)}
                    onChange={(e) => handleEdit('stats', `${index}.number`, e.target.value)}
                    style={{
                      fontSize: '48px',
                      fontWeight: '800',
                      marginBottom: '8px',
                      background: 'rgba(255,255,255,0.2)',
                      border: '2px solid white',
                      borderRadius: '6px',
                      padding: '8px',
                      color: 'white',
                      textAlign: 'center',
                      width: '100%'
                    }}
                  />
                ) : (
                  <div style={{
                    fontSize: '48px',
                    fontWeight: '800',
                    marginBottom: '8px'
                  }}>
                    {stat.number}
                  </div>
                )}
                {isEditMode ? (
                  <input
                    type="text"
                    value={getEditedValue('stats', `${index}.label`)}
                    onChange={(e) => handleEdit('stats', `${index}.label`, e.target.value)}
                    style={{
                      fontSize: '16px',
                      background: 'rgba(255,255,255,0.2)',
                      border: '2px solid white',
                      borderRadius: '6px',
                      padding: '6px',
                      color: 'white',
                      textAlign: 'center',
                      width: '100%'
                    }}
                  />
                ) : (
                  <div style={{
                    fontSize: '16px',
                    opacity: 0.9,
                    fontWeight: '500'
                  }}>
                    {stat.label}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section
        ref={el => sectionRefs.current['cta'] = el}
        data-section="cta"
        style={{
          minHeight: '60vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#f7fafc',
          padding: '80px 20px'
        }}
      >
        <div style={{
          textAlign: 'center',
          maxWidth: '800px',
          opacity: visibleSections['cta'] ? 1 : 0,
          transform: visibleSections['cta'] ? 'translateY(0)' : 'translateY(30px)',
          transition: 'all 0.8s ease'
        }}>
          {isEditMode ? (
            <input
              type="text"
              value={getEditedValue('cta', 'title')}
              onChange={(e) => handleEdit('cta', 'title', e.target.value)}
              style={{
                fontSize: '48px',
                fontWeight: '700',
                marginBottom: '24px',
                width: '100%',
                border: '2px solid #3b82f6',
                borderRadius: '8px',
                padding: '10px',
                color: '#2d3748'
              }}
            />
          ) : (
            <h2 style={{
              fontSize: '48px',
              fontWeight: '700',
              marginBottom: '24px',
              color: '#2d3748'
            }}>
              {content.cta.title}
            </h2>
          )}
          {isEditMode ? (
            <textarea
              value={getEditedValue('cta', 'subtitle')}
              onChange={(e) => handleEdit('cta', 'subtitle', e.target.value)}
              style={{
                fontSize: '20px',
                color: '#718096',
                marginBottom: '48px',
                lineHeight: '1.8',
                width: '100%',
                border: '2px solid #3b82f6',
                borderRadius: '8px',
                padding: '15px',
                minHeight: '80px',
                resize: 'vertical'
              }}
            />
          ) : (
            <p style={{
              fontSize: '20px',
              color: '#718096',
              marginBottom: '48px',
              lineHeight: '1.8'
            }}>
              {content.cta.subtitle}
            </p>
          )}
          <button
            onClick={handleGetStarted}
            style={{
              padding: '20px 60px',
              fontSize: '20px',
              fontWeight: '600',
              color: 'white',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              border: 'none',
              borderRadius: '50px',
              cursor: 'pointer',
              boxShadow: '0 10px 30px rgba(102, 126, 234, 0.4)',
              transition: 'all 0.3s ease'
            }}
            onMouseEnter={(e) => {
              e.target.style.transform = 'scale(1.05) translateY(-2px)';
              e.target.style.boxShadow = '0 15px 40px rgba(102, 126, 234, 0.5)';
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = 'scale(1) translateY(0)';
              e.target.style.boxShadow = '0 10px 30px rgba(102, 126, 234, 0.4)';
            }}
          >
            {isEditMode ? (
              <input
                type="text"
                value={getEditedValue('cta', 'buttonText')}
                onChange={(e) => {
                  e.stopPropagation();
                  handleEdit('cta', 'buttonText', e.target.value);
                }}
                onClick={(e) => e.stopPropagation()}
                style={{
                  background: 'rgba(255,255,255,0.3)',
                  border: '2px solid white',
                  borderRadius: '6px',
                  padding: '4px 8px',
                  color: 'white',
                  fontSize: '20px',
                  fontWeight: '600'
                }}
              />
            ) : (
              content.cta.buttonText
            )}
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        backgroundColor: '#2d3748',
        color: 'white',
        padding: '40px 20px',
        textAlign: 'center'
      }}>
        <p style={{
          fontSize: '14px',
          opacity: 0.8,
          margin: 0
        }}>
          © 2026 Traffic Monitor. All rights reserved.
        </p>
      </footer>

      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-20px); }
        }
        @keyframes bounce {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        @keyframes twinkle {
          0%, 100% { opacity: 0; }
          50% { opacity: 1; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes slideInLeft {
          from {
            opacity: 0;
            transform: translateX(-100px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
        @keyframes slideInRight {
          from {
            opacity: 0;
            transform: translateX(100px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(50px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes scaleIn {
          from {
            opacity: 0;
            transform: scale(0.8);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        
        /* Responsive carousel */
        @media (max-width: 1200px) {
          .carousel-slide {
            flex: 0 0 100%;
          }
        }
        
        @media (max-width: 768px) {
          .carousel-controls {
            padding: 0 10px;
          }
          
          .carousel-controls button {
            width: 40px;
            height: 40px;
            font-size: 16px;
          }
        }
      `}</style>
    </div>
  );
}

export default LandingPage;