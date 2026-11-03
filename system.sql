-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: localhost    Database: inventory_system
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `app_notifications`
--

DROP TABLE IF EXISTS `app_notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `app_notifications` (
  `notification_id` int NOT NULL AUTO_INCREMENT,
  `recipient_user_id` int NOT NULL,
  `event_id` int NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `read_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`notification_id`),
  UNIQUE KEY `uq_notifications_recipient_event` (`recipient_user_id`,`event_id`),
  KEY `ix_notifications_recipient_read_time` (`recipient_user_id`,`read_at`,`created_at`),
  KEY `fk_notifications_event` (`event_id`),
  CONSTRAINT `fk_notifications_event` FOREIGN KEY (`event_id`) REFERENCES `product_request_events` (`event_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_notifications_recipient` FOREIGN KEY (`recipient_user_id`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `app_notifications`
--

LOCK TABLES `app_notifications` WRITE;
/*!40000 ALTER TABLE `app_notifications` DISABLE KEYS */;
/*!40000 ALTER TABLE `app_notifications` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `product_audit_events`
--

DROP TABLE IF EXISTS `product_audit_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `product_audit_events` (
  `event_id` int NOT NULL AUTO_INCREMENT,
  `product_id` int NOT NULL,
  `actor_user_id` int NOT NULL,
  `actor_role` enum('Admin','Super Admin') NOT NULL,
  `event_type` enum('DirectAdded','Edited','StockChanged','Archived') NOT NULL,
  `event_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `product_name_before` varchar(100) DEFAULT NULL,
  `product_name_after` varchar(100) DEFAULT NULL,
  `quantity_before` int DEFAULT NULL,
  `quantity_after` int DEFAULT NULL,
  `price_before` decimal(10,2) DEFAULT NULL,
  `price_after` decimal(10,2) DEFAULT NULL,
  `product_status_before` enum('Active','Approval Pending','Archived') DEFAULT NULL,
  `product_status_after` enum('Active','Approval Pending','Archived') DEFAULT NULL,
  PRIMARY KEY (`event_id`),
  KEY `ix_product_audit_product_time` (`product_id`,`event_at`,`event_id`),
  KEY `ix_product_audit_actor_time` (`actor_user_id`,`event_at`),
  CONSTRAINT `fk_product_audit_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_product_audit_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `product_audit_events`
--

LOCK TABLES `product_audit_events` WRITE;
/*!40000 ALTER TABLE `product_audit_events` DISABLE KEYS */;
/*!40000 ALTER TABLE `product_audit_events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `product_request_events`
--

DROP TABLE IF EXISTS `product_request_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `product_request_events` (
  `event_id` int NOT NULL AUTO_INCREMENT,
  `request_id` int NOT NULL,
  `product_id` int DEFAULT NULL,
  `actor_user_id` int NOT NULL,
  `actor_role` enum('Staff','Admin','Super Admin') NOT NULL,
  `event_type` enum('Submitted','ApprovedAsRequested','ApprovedWithChanges','Rejected') NOT NULL,
  `event_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `product_name_snapshot` varchar(100) NOT NULL,
  `requested_quantity_snapshot` int NOT NULL,
  `requested_price_snapshot` decimal(10,2) NOT NULL,
  `approved_quantity_snapshot` int DEFAULT NULL,
  `approved_price_snapshot` decimal(10,2) DEFAULT NULL,
  `decision_note` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`event_id`),
  KEY `ix_request_events_request_time` (`request_id`,`event_at`,`event_id`),
  KEY `ix_request_events_actor_time` (`actor_user_id`,`event_at`),
  KEY `ix_request_events_product` (`product_id`),
  CONSTRAINT `fk_request_events_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_request_events_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_request_events_request` FOREIGN KEY (`request_id`) REFERENCES `product_requests` (`request_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `product_request_events`
--

LOCK TABLES `product_request_events` WRITE;
/*!40000 ALTER TABLE `product_request_events` DISABLE KEYS */;
/*!40000 ALTER TABLE `product_request_events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `product_requests`
--

DROP TABLE IF EXISTS `product_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `product_requests` (
  `request_id` int NOT NULL AUTO_INCREMENT,
  `linked_product_id` int DEFAULT NULL,
  `product_name` varchar(100) NOT NULL,
  `requested_quantity` int NOT NULL,
  `requested_price` decimal(10,2) NOT NULL,
  `approved_quantity` int DEFAULT NULL,
  `approved_price` decimal(10,2) DEFAULT NULL,
  `status` enum('Pending','Approved','Rejected') NOT NULL DEFAULT 'Pending',
  `requested_by` int NOT NULL,
  `requested_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `reviewed_by` int DEFAULT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `decision_note` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`request_id`),
  UNIQUE KEY `uq_product_requests_linked_product` (`linked_product_id`),
  KEY `ix_product_requests_status_time` (`status`,`requested_at`,`request_id`),
  KEY `ix_product_requests_requester_time` (`requested_by`,`requested_at`,`request_id`),
  KEY `ix_product_requests_reviewer_time` (`reviewed_by`,`reviewed_at`,`request_id`),
  CONSTRAINT `fk_product_requests_product` FOREIGN KEY (`linked_product_id`) REFERENCES `products` (`product_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_product_requests_requester` FOREIGN KEY (`requested_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_product_requests_reviewer` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `product_requests`
--

LOCK TABLES `product_requests` WRITE;
/*!40000 ALTER TABLE `product_requests` DISABLE KEYS */;
/*!40000 ALTER TABLE `product_requests` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `products`
--

DROP TABLE IF EXISTS `products`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `products` (
  `product_id` int NOT NULL AUTO_INCREMENT,
  `product_name` varchar(100) NOT NULL,
  `quantity` int NOT NULL DEFAULT '0',
  `price` decimal(10,2) NOT NULL DEFAULT '0.00',
  PRIMARY KEY (`product_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `products`
--

LOCK TABLES `products` WRITE;
/*!40000 ALTER TABLE `products` DISABLE KEYS */;
/*!40000 ALTER TABLE `products` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('Admin','Super Admin','Staff') NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `super_admin_guard` tinyint GENERATED ALWAYS AS ((case when (`role` = _utf8mb4'Super Admin') then 1 else NULL end)) STORED,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `uq_users_single_super_admin` (`super_admin_guard`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` (`user_id`, `username`, `password_hash`, `role`, `is_active`) VALUES (1,'root','$2b$12$p/Qq3eBqZlKFofULWCyzw.qvG0zJLm4g.yKhycC5wNTnPOK2415Aq','Super Admin',1),(2,'Admin','$2b$12$4SJCCSdm8l8vsu7VubLe2OpwlD5je.Bjh0gHqi2F9uKvZ5nTUQXN.','Admin',1),(3,'Staff','$2b$12$4SJCCSdm8l8vsu7VubLe2OpwlD5je.Bjh0gHqi2F9uKvZ5nTUQXN.','Staff',1);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-11-04  6:38:40
