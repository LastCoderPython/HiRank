export interface College {
  id: string;
  name: string;
  location: string;
  type: 'government' | 'private';
  avgFees: string;
  matchPercentage: number;
  exam: string;
  image: string;
  courses: string[];
  ranking: number;
  placementRate: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  colleges?: College[];
}

export interface ChatThread {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  preview: string;
}

export const mockColleges: College[] = [
  {
    id: '1',
    name: 'Assam Engineering College (AEC)',
    location: 'Guwahati, Assam',
    type: 'government',
    avgFees: '₹12,000',
    matchPercentage: 95,
    exam: 'Assam CEE',
    image: '/colleges/aec.jpg',
    courses: ['Computer Science', 'Electrical', 'Mechanical', 'Civil'],
    ranking: 1,
    placementRate: '85%'
  },
  {
    id: '2',
    name: 'Jorhat Engineering College',
    location: 'Jorhat, Assam',
    type: 'government',
    avgFees: '₹15,000',
    matchPercentage: 88,
    exam: 'Assam CEE',
    image: '/colleges/jec.jpg',
    courses: ['Computer Science', 'Electronics', 'Mechanical'],
    ranking: 2,
    placementRate: '78%'
  },
  {
    id: '3',
    name: 'Gauhati University Institute of Science and Technology',
    location: 'Guwahati, Assam',
    type: 'government',
    avgFees: '₹18,000',
    matchPercentage: 82,
    exam: 'Assam CEE',
    image: '/colleges/guist.jpg',
    courses: ['Computer Science', 'Electronics', 'Biotechnology'],
    ranking: 3,
    placementRate: '75%'
  },
  {
    id: '4',
    name: 'Dibrugarh University Institute of Engineering and Technology',
    location: 'Dibrugarh, Assam',
    type: 'government',
    avgFees: '₹14,000',
    matchPercentage: 78,
    exam: 'Assam CEE',
    image: '/colleges/duiet.jpg',
    courses: ['Computer Science', 'Mechanical', 'Civil'],
    ranking: 4,
    placementRate: '72%'
  },
  {
    id: '5',
    name: 'Assam University, Silchar',
    location: 'Silchar, Assam',
    type: 'government',
    avgFees: '₹20,000',
    matchPercentage: 72,
    exam: 'Assam CEE',
    image: '/colleges/aus.jpg',
    courses: ['Computer Science', 'Electronics', 'Information Technology'],
    ranking: 5,
    placementRate: '68%'
  }
];

export const mockChatThreads: ChatThread[] = [
  {
    id: '1',
    title: 'Assam CEE Engineering Options',
    lastMessage: 'Based on your rank of 1500...',
    timestamp: new Date(Date.now() - 1000 * 60 * 30),
    preview: 'Computer Science government colleges'
  },
  {
    id: '2',
    title: 'JEE Mains NIT Possibilities',
    lastMessage: 'With 95 percentile in JEE...',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2),
    preview: 'NIT admission chances'
  }
];

export const mockChatMessages: ChatMessage[] = [
  {
    id: '1',
    role: 'user',
    content: 'I got 1500 rank in Assam CEE. Can I get Computer Science in a government college?',
    timestamp: new Date(Date.now() - 1000 * 60 * 5)
  },
  {
    id: '2',
    role: 'assistant',
    content: 'Based on previous year cutoffs, here are your top matches for Computer Science:',
    timestamp: new Date(Date.now() - 1000 * 60 * 4),
    colleges: mockColleges.slice(0, 3)
  }
];

export const suggestionChips = [
  { icon: 'trending_up', text: 'I got 4500 rank in CEE...' },
  { icon: 'school', text: 'Best engineering colleges with 12th marks in Assam' },
  { icon: 'analytics', text: 'JEE Mains cutoff for NIT Silchar' },
  { icon: 'engineering', text: 'CEE vs JEE - which is better for me?' }
];
