import { createRouter, createWebHistory } from 'vue-router'
import Connections from '../views/Connections.vue'

const routes = [
  {
    path: '/',
    component: Connections,
    // children: [
    //   {
    //     path: '/',
    //     name: 'Home',
    //     component: Home,
    //     meta: { requiresAuth: false },
    //   },
    //   {
    //     path: '/hotel/:id',
    //     name: 'Hotel',
    //     component: HotelDetail,
    //     meta: { requiresAuth: false },
    //   },
    //   {
    //     path: '/hotel/:id/edit',
    //     name: 'EditHotel',
    //     component: EditHotel,
    //     meta: { requiresAuth: true },
    //   },
    //   {
    //     path: '/hotel/create',
    //     name: 'CreateHotel',
    //     component: CreateHotelForm,
    //     meta: { requiresAuth: true },
    //   },
    //   {
    //     path: '/book/:id',
    //     name: 'BookHotel',
    //     component: BookHotel,
    //     meta: { requiresAuth: true },
    //   },
    //   {
    //     path: '/my-reservations',
    //     name: 'MyReservations',
    //     component: MyReservations,
    //     meta: { requiresAuth: true },
    //   },
    //   {
    //     path: '/manage-reservations',
    //     name: 'ManageReservations',
    //     component: ManageReservations,
    //     meta: { requiresAuth: true },
    //   },
    //   {
    //     path: '/about',
    //     name: 'About',
    //     component: AboutView,
    //     meta: { requiresAuth: false },
    //   },
    // ],
  },
  // {
  //   path: '/login',
  //   name: 'LogIn',
  //   component: Login,
  //   meta: { requiresAuth: false },
  // },
  // {
  //   path: '/signup',
  //   name: 'SignUp',
  //   component: Signup,
  //   meta: { requiresAuth: false },
  // },
  // {
  //   path: '/:pathMatch(.*)*',
  //   name: 'NotFound',
  //   component: NotFound,
  //   meta: { requiresAuth: false },
  // },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
