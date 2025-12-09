//src/pages/LandingPage.js
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function LandingPage() {
  const navigate = useNavigate();
  const [currentFeature, setCurrentFeature] = useState(0);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  const features = [
    {
      title: "Real-Time Traffic Analysis",
      description: "Monitor traffic patterns and congestion levels across multiple locations with advanced AI-powered video analysis.",
      icon: "🚦"
    },
    {
      title: "Smart Data Visualization",
      description: "View comprehensive traffic reports with interactive charts and graphs that update in real-time.",
      icon: "📊"
    },
    {
      title: "Peak Hour Detection",
      description: "Automatically identify morning and evening rush hours to optimize traffic management strategies.",
      icon: "⏰"
    },
    {
      title: "Historical Insights",
      description: "Access weekly trends and patterns to make data-driven decisions for urban planning.",
      icon: "📈"
    }
  ];

  const teamMembers = [
    {
      name: "Traffic Analytics Team",
      role: "Developing intelligent solutions for urban mobility",
      description: "We're passionate about using technology to solve real-world traffic challenges."
    }
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentFeature((prev) => (prev + 1) % features.length);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleGetStarted = () => {
    navigate('/home');
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#ffffff',
      overflow: 'auto'
    }}>
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
        {/* Animated background elements */}
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
            animation: 'float 3s ease-in-out infinite'
          }}>
            🚗
          </div>
          <h1 style={{
            fontSize: '64px',
            fontWeight: '800',
            marginBottom: '24px',
            textShadow: '2px 2px 4px rgba(0,0,0,0.2)',
            letterSpacing: '-1px'
          }}>
            Traffic Monitor
          </h1>
          <p style={{
            fontSize: '24px',
            marginBottom: '48px',
            opacity: 0.95,
            lineHeight: '1.6',
            fontWeight: '300'
          }}>
            Advanced AI-Powered Traffic Analysis System
          </p>
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
          
          {/* Scroll indicator */}
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
        `}</style>
      </section>

      {/* Features Carousel Section */}
      <section style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#f7fafc',
        padding: '80px 20px'
      }}>
        <div style={{
          maxWidth: '1200px',
          width: '100%'
        }}>
          <h2 style={{
            fontSize: '48px',
            fontWeight: '700',
            textAlign: 'center',
            marginBottom: '60px',
            color: '#2d3748'
          }}>
            What Our System Does
          </h2>

          {/* Carousel */}
          <div style={{
            position: 'relative',
            backgroundColor: 'white',
            borderRadius: '20px',
            padding: '60px 40px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.1)',
            minHeight: '400px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <div style={{
              fontSize: '80px',
              marginBottom: '24px',
              transition: 'all 0.5s ease'
            }}>
              {features[currentFeature].icon}
            </div>
            <h3 style={{
              fontSize: '32px',
              fontWeight: '600',
              marginBottom: '16px',
              color: '#2d3748',
              transition: 'all 0.5s ease'
            }}>
              {features[currentFeature].title}
            </h3>
            <p style={{
              fontSize: '18px',
              color: '#718096',
              textAlign: 'center',
              maxWidth: '600px',
              lineHeight: '1.8',
              transition: 'all 0.5s ease'
            }}>
              {features[currentFeature].description}
            </p>

            {/* Carousel indicators */}
            <div style={{
              display: 'flex',
              gap: '12px',
              marginTop: '40px'
            }}>
              {features.map((_, index) => (
                <button
                  key={index}
                  onClick={() => setCurrentFeature(index)}
                  style={{
                    width: index === currentFeature ? '40px' : '12px',
                    height: '12px',
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: index === currentFeature ? '#667eea' : '#cbd5e0',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease'
                  }}
                />
              ))}
            </div>
          </div>

          {/* Feature Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: '24px',
            marginTop: '60px'
          }}>
            {features.map((feature, index) => (
              <div
                key={index}
                style={{
                  backgroundColor: 'white',
                  padding: '32px',
                  borderRadius: '12px',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
                  transition: 'all 0.3s ease',
                  cursor: 'pointer',
                  border: '2px solid transparent'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-8px)';
                  e.currentTarget.style.boxShadow = '0 12px 24px rgba(0,0,0,0.1)';
                  e.currentTarget.style.borderColor = '#667eea';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.05)';
                  e.currentTarget.style.borderColor = 'transparent';
                }}
              >
                <div style={{ fontSize: '40px', marginBottom: '16px' }}>
                  {feature.icon}
                </div>
                <h4 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  marginBottom: '8px',
                  color: '#2d3748'
                }}>
                  {feature.title}
                </h4>
                <p style={{
                  fontSize: '14px',
                  color: '#718096',
                  lineHeight: '1.6'
                }}>
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* About Us Section */}
      <section style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        padding: '80px 20px'
      }}>
        <div style={{
          maxWidth: '1200px',
          width: '100%'
        }}>
          <h2 style={{
            fontSize: '48px',
            fontWeight: '700',
            textAlign: 'center',
            marginBottom: '32px'
          }}>
            About Us
          </h2>
          
          <div style={{
            backgroundColor: 'rgba(255,255,255,0.1)',
            backdropFilter: 'blur(10px)',
            borderRadius: '20px',
            padding: '60px 40px',
            textAlign: 'center',
            marginBottom: '60px'
          }}>
            <p style={{
              fontSize: '24px',
              lineHeight: '1.8',
              maxWidth: '800px',
              margin: '0 auto 40px',
              fontWeight: '300'
            }}>
              We are a dedicated team of developers and data scientists committed to revolutionizing 
              urban traffic management through cutting-edge technology and artificial intelligence.
            </p>
            <p style={{
              fontSize: '18px',
              lineHeight: '1.8',
              maxWidth: '800px',
              margin: '0 auto',
              opacity: 0.9
            }}>
              Our mission is to create smarter cities by providing actionable insights from traffic 
              data, helping urban planners and traffic managers make informed decisions that improve 
              the daily commute for millions of people.
            </p>
          </div>

          {/* Stats */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '32px',
            marginTop: '60px'
          }}>
            {[
              { number: '1M+', label: 'Vehicles Analyzed' },
              { number: '24/7', label: 'Real-time Monitoring' },
              { number: '99.9%', label: 'Accuracy Rate' },
              { number: '100+', label: 'Locations Tracked' }
            ].map((stat, index) => (
              <div
                key={index}
                style={{
                  textAlign: 'center',
                  padding: '32px',
                  backgroundColor: 'rgba(255,255,255,0.15)',
                  borderRadius: '12px',
                  backdropFilter: 'blur(10px)'
                }}
              >
                <div style={{
                  fontSize: '48px',
                  fontWeight: '800',
                  marginBottom: '8px'
                }}>
                  {stat.number}
                </div>
                <div style={{
                  fontSize: '16px',
                  opacity: 0.9,
                  fontWeight: '500'
                }}>
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section style={{
        minHeight: '60vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#f7fafc',
        padding: '80px 20px'
      }}>
        <div style={{
          textAlign: 'center',
          maxWidth: '800px'
        }}>
          <h2 style={{
            fontSize: '48px',
            fontWeight: '700',
            marginBottom: '24px',
            color: '#2d3748'
          }}>
            Ready to Transform Traffic Management?
          </h2>
          <p style={{
            fontSize: '20px',
            color: '#718096',
            marginBottom: '48px',
            lineHeight: '1.8'
          }}>
            Start analyzing traffic patterns and gain valuable insights with our advanced AI system.
          </p>
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
            Begin Your Journey →
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
          © 2024 Traffic Monitor. All rights reserved.
        </p>
      </footer>
    </div>
  );
}

export default LandingPage;